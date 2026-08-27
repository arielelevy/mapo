"""Un regulador adaptativo en el cliente, porque reintentar no alcanza.

EL PROBLEMA QUE EL REINTENTO NO RESUELVE. `map_reduce` sobre un corpus de 483k tokens gasta
343.682 tokens en 49 llamadas seguidas. Eso no roza el limite de TPM: lo revienta. Y cuando
la cuota queda agotada, el limite es SOSTENIDO -- todo lo que viene atras se come un 429
durante la ventana entera. Reintentar cinco veces con backoff es la respuesta correcta a un
pico y la respuesta equivocada a una cuota agotada: los cinco intentos caen dentro de la
misma ventana y fallan los cinco.

Un cliente que va a exceder la cuota tiene que MARCAR EL PASO, no dispararla y reintentar.

POR QUE ADAPTATIVO. No se cual es la cuota del deployment, y no quiero una constante en el
codigo que quede mintiendo cuando alguien cambie el SKU. Asi que el cliente la aprende:
AIMD, como el control de congestion de TCP y por la misma razon. Un 429 es la unica senal
confiable de que se paso, asi que baja multiplicativamente ante 429 y sube aditivamente
mientras no haya. Converge sin que nadie le diga el numero.

Y EL PRESUPUESTO DE REINTENTO PASA A SER TIEMPO, NO INTENTOS. Contar intentos mide el
esfuerzo del cliente; lo que importa es si la ventana de la cuota alcanzo a rotar. Cinco
intentos pueden ser 6 segundos o 6 minutos, y la diferencia es justamente la que decide si
sobrevive.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for label, old, new in pairs:
        if old not in s:
            sys.exit(f"FAIL {path}/{label}: ancla ausente")
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print(f"  {path}: {len(pairs)} bloques")


patch("app/llm.py", [
    (
        "throttle",
        "def backoff_seconds(attempt: int, retry_after: str | None) -> float:",
        '''# The retry budget is TIME, not attempts. Counting attempts measures the client's
# effort; what decides survival is whether the provider's quota window had a chance to
# roll over, and five attempts can be six seconds or six minutes.
RETRY_BUDGET_SECONDS = 420.0

# AIMD, as in TCP congestion control and for the same reason: the only reliable signal
# that we exceeded a quota we cannot read is being told so. Start optimistic, halve on a
# 429, recover slowly while there are none.
_INITIAL_TOKENS_PER_SECOND = 3000.0
_MIN_TOKENS_PER_SECOND = 150.0
_RECOVERY_FACTOR = 1.05
_DECREASE_FACTOR = 0.5
_BURST_SECONDS = 2.0


class _Throttle:
    """Shared, self-tuning pace limiter over estimated tokens.

    A leaky bucket rather than a fixed sleep: a run that is mostly small calls should not
    be slowed at all, and one 343k-token paradigm should not be allowed to spend the
    whole minute's quota in one breath and leave every other row to fail.

    Shared across threads on purpose. A per-worker limiter cannot see that the quota is
    global, which is exactly the mistake that made two workers enough to break it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rate = _INITIAL_TOKENS_PER_SECOND
        self._available = _INITIAL_TOKENS_PER_SECOND * _BURST_SECONDS
        self._last = time.monotonic()
        self.throttled_seconds = 0.0
        self.limit_events = 0

    def _refill(self) -> None:
        now = time.monotonic()
        self._available = min(
            self._rate * _BURST_SECONDS,
            self._available + self._rate * (now - self._last),
        )
        self._last = now

    def acquire(self, estimated_tokens: int) -> None:
        """Block until the pace allows a request of roughly this size."""
        # A single call larger than the whole burst must not deadlock: it is allowed
        # through once the bucket is as full as it will ever get, and the cost of it
        # overshooting is one 429 that teaches the rate.
        want = min(float(estimated_tokens), self._rate * _BURST_SECONDS)
        while True:
            with self._lock:
                self._refill()
                if self._available >= want:
                    self._available -= want
                    return
                deficit = want - self._available
                wait = deficit / max(self._rate, 1.0)
            self.throttled_seconds += wait
            time.sleep(min(wait, 30.0))

    def on_rate_limited(self) -> None:
        with self._lock:
            self._rate = max(_MIN_TOKENS_PER_SECOND, self._rate * _DECREASE_FACTOR)
            # Drain the bucket too. Otherwise the burst allowance lets the next few calls
            # through at the old pace and earns another 429 immediately.
            self._available = 0.0
            self.limit_events += 1

    def on_success(self) -> None:
        with self._lock:
            self._rate = min(
                _INITIAL_TOKENS_PER_SECOND, self._rate * _RECOVERY_FACTOR
            )

    def describe(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tokens_per_second": round(self._rate, 1),
                "limit_events": self.limit_events,
                "throttled_seconds": round(self.throttled_seconds, 1),
            }


THROTTLE = _Throttle()


def estimate_tokens(payload: dict[str, Any]) -> int:
    """Rough token count for pacing. Deliberately crude -- it only sets a pace."""
    text = 0
    for message in payload.get("messages", ()):
        content = message.get("content")
        if isinstance(content, str):
            text += len(content)
    return text // 4 + int(payload.get("max_completion_tokens", 0) or 0)


def backoff_seconds(attempt: int, retry_after: str | None) -> float:''',
    ),
    (
        "retry-loop",
        '''    response = None
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
        '''    THROTTLE.acquire(estimate_tokens(payload))

    response = None
    started = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        # Out of patience when the next wait would run past the budget. Checking before
        # sleeping rather than after keeps the caller's wall-clock bounded, which matters
        # because a study that hangs is worse than one that records a failure.
        spent = time.monotonic() - started
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError):
            wait = backoff_seconds(attempt, None)
            if spent + wait > RETRY_BUDGET_SECONDS:
                raise
            time.sleep(wait)
            continue

        if response.status_code not in RETRYABLE_STATUS:
            THROTTLE.on_success()
            return response, attempt

        if response.status_code == 429:
            THROTTLE.on_rate_limited()
        wait = backoff_seconds(attempt, response.headers.get("retry-after"))
        if spent + wait > RETRY_BUDGET_SECONDS:
            return response, attempt
        time.sleep(wait)''',
    ),
    (
        "threading-import",
        "import random",
        "import random\nimport threading",
    ),
])

print("listo")
