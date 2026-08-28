"""Un solo reintento, usado por los dos clientes.

EL PROBLEMA. Habia dos implementaciones del mismo backoff. `llm.py` tenia la buena
(Retry-After, jitter, tope de 60s) y `embeddings.py` una copia peor que yo escribi sin
mirar la que ya existia: sin tope, asi que un Retry-After largo dormia lo que dijera --
eso fue lo que trabo el precalentamiento a mitad de camino. Y sin reintento ante error de
transporte, que la otra si tenia.

Y la buena tambien tenia un agujero: al respetar Retry-After devolvia el valor exacto, sin
jitter. Su propio docstring dice que sin jitter los workers limitados en el mismo instante
reintentan en lockstep y se vuelven a limitar entre ellos -- y es exactamente lo que pasa
cuando el servidor les manda a todos el MISMO Retry-After. El jitter hace falta mas en ese
camino que en el otro, no menos.

Queda una funcion de modulo, `backoff_seconds`, y un helper `request_with_retry` que
encapsula el bucle completo (transporte + status), de modo que agregar un cliente nuevo no
sea agregar un tercer reintento.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent


# Guarda de idempotencia. Esto es una migracion de una sola vez, no una herramienta:
# sus anclas siguen matcheando el archivo YA parcheado, asi que una segunda corrida
# duplica el fragmento (y deja el modulo con SyntaxError) antes de abortar en un ancla
# posterior. Se rechaza de entrada, y ademas se verifican TODAS las anclas antes de
# escribir cualquier archivo.
def refuse_if_applied(markers):
    done = [p for p, m in markers if m in (ROOT / p).read_text(encoding="utf-8")]
    if done:
        sys.exit("YA APLICADO en " + ", ".join(done) + ": no se toca nada.")


refuse_if_applied([
    ("app/llm.py", "MAX_BACKOFF_SECONDS"),
])



def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for label, old, new in pairs:
        if old not in s:
            sys.exit(f"FAIL {path}/{label}: ancla ausente")
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print(f"  {path}: {len(pairs)} bloques")


# ---------------------------------------------------------------- llm.py

patch("app/llm.py", [
    # 1. La funcion de modulo, con jitter en AMBOS caminos.
    (
        "module-level-backoff",
        "RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})\n"
        "MAX_ATTEMPTS = 5\n"
        "BASE_BACKOFF_SECONDS = 2.0",
        '''RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 2.0
# A server that is rate limiting can name a wait far longer than any run should absorb.
# Honour the hint, but not without a ceiling: an unbounded sleep is indistinguishable
# from a hang, and it stalled a cache warm-up here before this cap existed.
MAX_BACKOFF_SECONDS = 60.0


def backoff_seconds(attempt: int, retry_after: str | None) -> float:
    """How long to wait before retrying attempt `attempt`.

    Honours Retry-After when the server sends one, else exponential. Jitter is applied
    to BOTH paths, and the Retry-After path is where it matters most: when several
    workers are limited at the same instant the server hands them all the SAME hint, so
    obeying it exactly is what puts them back in lockstep to rate-limit each other again.

    Single implementation on purpose. There were two, and the copy drifted worse than
    the original.
    """
    base = MAX_BACKOFF_SECONDS
    if retry_after:
        try:
            base = min(MAX_BACKOFF_SECONDS, float(retry_after))
        except ValueError:
            base = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
    else:
        base = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
    return base * (0.5 + random.random())


def request_with_retry(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> tuple["httpx.Response", int]:
    """POST with retry on transport failure and on retryable status.

    Returns the last response and the number of attempts made. Does NOT call
    raise_for_status: the caller decides what a final non-2xx means, which differs
    between a completion and an embedding.

    Every client goes through here. Adding a third client must not mean adding a third
    retry loop -- that is how the two drifted apart.
    """
    response = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(backoff_seconds(attempt, None))
            continue

        if response.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
            return response, attempt
        time.sleep(backoff_seconds(attempt, response.headers.get("retry-after")))

    return response, MAX_ATTEMPTS''',
    ),
    # 2. El cliente de chat usa el helper en vez de su propio bucle.
    (
        "chat-uses-helper",
        """        response = None
        attempts = 0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            attempts = attempt
            try:
                response = httpx.post(
                    self._url,
                    headers=headers,
                    json=payload,
                    timeout=self._settings.request_timeout,
                )
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == MAX_ATTEMPTS:
                    raise
                time.sleep(self._backoff(attempt, None))
                continue

            if response.status_code not in RETRYABLE_STATUS:
                break
            if attempt == MAX_ATTEMPTS:
                break
            time.sleep(self._backoff(attempt, response.headers.get("retry-after")))
""",
        """        response, attempts = request_with_retry(
            self._url, headers, payload, self._settings.request_timeout
        )
""",
    ),
    # 3. Fuera el staticmethod duplicado. Sin alias de compatibilidad.
    (
        "drop-staticmethod",
        '''    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        """Honour Retry-After when the server sends one, else exponential with jitter.

        Jitter is not decoration: without it, concurrent workers rate-limited at the
        same moment retry in lockstep and rate-limit each other again.
        """
        if retry_after:
            try:
                return min(60.0, float(retry_after))
            except ValueError:
                pass
        return min(60.0, BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))) * (
            0.5 + random.random()
        )

''',
        "",
    ),
])

# ---------------------------------------------------------------- embeddings.py

patch("app/embeddings.py", [
    (
        "use-shared-retry",
        """        response = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            response = httpx.post(
                self._url,
                headers={
                    "api-key": self._settings.api_key,
                    "Content-Type": "application/json",
                },
                json={"input": text},
                timeout=self._settings.request_timeout,
            )
            if response.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
                break
            # Azure states how long to wait on a 429. Backing off 2 seconds when it asked
            # for 60 guarantees the next 429, so the header wins when it is present.
            wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            hinted = response.headers.get("retry-after")
            if hinted:
                try:
                    wait = max(wait, float(hinted))
                except ValueError:
                    pass
            # Jitter: with several workers the threads back off on the same schedule and
            # collide again on the retry. Spreading them is what actually clears a burst.
            time.sleep(wait * (1.0 + random.random() * 0.5))

        response.raise_for_status()""",
        """        # Same retry as the chat client, because it is the same failure. This used to
        # be a separate copy and the copy was worse: it had no ceiling on Retry-After,
        # so a long hint slept for as long as the server named and looked like a hang.
        response, _ = request_with_retry(
            self._url,
            {
                "api-key": self._settings.api_key,
                "Content-Type": "application/json",
            },
            {"input": text},
            self._settings.request_timeout,
        )
        response.raise_for_status()""",
    ),
    (
        "imports",
        "from .llm import BASE_BACKOFF_SECONDS, MAX_ATTEMPTS, RETRYABLE_STATUS",
        "from .llm import request_with_retry",
    ),
])

print("listo")
