"""Direct Azure OpenAI chat client.

No SDK, no agent framework. Two reasons, both experimental rather than aesthetic:

1. Frameworks inject their own prompts, retries and parsing. Any of those becomes a
   confound: a paradigm would be measured together with its framework's opinions.
2. Determinism has to be controllable end to end. A framework that silently retries
   or reorders tool calls destroys replayability, which is the property under study.

Every completion is content-addressed and cached on disk. The cache is not an
optimisation detail — it is what makes a run replayable byte for byte, which is the
D3 (sealed) guarantee in `policy.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from dataclasses import dataclass, field, field as dc_field
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .fsio import write_atomic


# Transient by nature: rate limiting and server-side faults say nothing about the
# request. Anything else — 400, 401, 404 — is a bug in the request and must surface
# immediately rather than be retried into a timeout.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
# `MAX_ATTEMPTS` vivia aca y no lo leia nadie: es un resto del diseño anterior,
# contradicho por el comentario de ocho lineas mas abajo — el presupuesto de
# reintento es TIEMPO y no intentos, porque contar intentos mide la impaciencia
# del cliente y no la salud del endpoint. Una constante muerta que nombra un tope
# se lee como un tope que existe.
BASE_BACKOFF_SECONDS = 2.0
# A server that is rate limiting can name a wait far longer than any run should absorb.
# Honour the hint, but not without a ceiling: an unbounded sleep is indistinguishable
# from a hang, and it stalled a cache warm-up here before this cap existed.
MAX_BACKOFF_SECONDS = 60.0


# The retry budget is TIME, not attempts. Counting attempts measures the client's
# effort; what decides survival is whether the provider's quota window had a chance to
# roll over, and five attempts can be six seconds or six minutes.
#
# Env-overridable (explicitly, never silently): a cell whose spend exceeds the
# deployment's ENTIRE per-minute quota needs several quota windows to complete, and 420s
# is not enough for that. A refill run sets MAPO_RETRY_BUDGET_SECONDS for itself;
# absent the variable, the declared constant stands.
RETRY_BUDGET_SECONDS = (
    float(os.environ["MAPO_RETRY_BUDGET_SECONDS"])
    if "MAPO_RETRY_BUDGET_SECONDS" in os.environ
    else 420.0
)

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
                # Contabilizar lo que se DUERME, no lo que se calculo, y adentro del
                # lock. Con `wait` de 100 s se sumaban 100 y se dormian 30, y la vuelta
                # siguiente volvia a sumar: el contador inflaba el tiempo de throttle
                # sin que nada lo desmintiera. Y `+=` fuera del lock es lectura-
                # modificacion-escritura desde varios workers, que ademas pierde sumas.
                slept = min(wait, 30.0)
                self.throttled_seconds += slept
            time.sleep(slept)

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


def backoff_seconds(attempt: int, retry_after: str | None) -> float:
    """How long to wait before retrying attempt `attempt`.

    Honours Retry-After when the server sends one, else exponential. Jitter is applied
    to BOTH paths, and the Retry-After path is where it matters most: when several
    workers are limited at the same instant the server hands them all the SAME hint, so
    obeying it exactly is what puts them back in lockstep to rate-limit each other again.

    Single implementation on purpose. There were two, and the copy drifted worse than
    the original.
    """
    hint = None
    if retry_after:
        try:
            hint = float(retry_after)
        except ValueError:
            hint = None

    if hint is not None:
        # The server named a number. Jitter goes UPWARD only: waiting less than it asked
        # guarantees the next 429, which is the bug this function exists to stop. So the
        # hint is a floor, spread over [hint, 1.5*hint], then capped.
        # The ceiling clamps the HINT, not the jittered result. Clamping afterwards
        # collapses the spread to a constant exactly when every worker got the same
        # large hint -- reintroducing lockstep at the one moment it hurts most. The
        # effective maximum is therefore 1.5x the ceiling, which is still bounded.
        wait = min(MAX_BACKOFF_SECONDS, hint)
        return wait * (1.0 + random.random() * 0.5)

    # No hint: the delay is our own estimate, so jitter either side of it is fine and
    # spreading below is what actually decorrelates concurrent workers.
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
    THROTTLE.acquire(estimate_tokens(payload))

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
        time.sleep(wait)


# QUE DEPLOYMENTS SON DE RAZONAMIENTO. Se decide por el NOMBRE, y eso es fragil a
# proposito: la alternativa es una lista de deployments que hay que mantener a mano, y este
# repo ya pago dos veces el precio de una lista escrita a mano que quedo vieja.
#
# `gpt-5.6` en adelante es lo que la doc marca con el pie ^9^: «support the Chat Completions
# API and function tools, but not both at the same time unless `reasoning_effort` is
# `none`». `gpt-5.4-nano` esta en la misma tabla de modelos de razonamiento y NO tiene ese
# pie — acepta tools con su default, y de hecho acepta `temperature` explicita.
FAMILIAS_CON_TOOLS_Y_RAZONAMIENTO_EXCLUYENTES = ("gpt-5.6", "gpt-5.7", "gpt-6")


def _es_de_razonamiento(deployment: str) -> bool:
    """Si este deployment rechaza `tools` junto con un `reasoning_effort` distinto de `none`."""
    return deployment.startswith(FAMILIAS_CON_TOOLS_Y_RAZONAMIENTO_EXCLUYENTES)


class SealedCacheMiss(RuntimeError):
    """Raised when a sealed replay needs a completion that is not in the cache.

    In sealed mode a miss is a hard error and never a live call: silently going to
    the network would mean the "replay" produced fresh, unaudited content.
    """


def _ttft(raw_usage: dict[str, Any]) -> int:
    """Tiempo al primer token, en ms, del bloque `latency_checkpoint` de Azure.

    NO HACIA FALTA STREAMING, que es lo que yo habia concluido. El proveedor lo devuelve
    en el objeto `usage` de una respuesta normal —`user_visible_ttft_ms`— y esta en las
    400/400 entradas de cache que se revisaron. Dije que medirlo exigia `stream=true` y
    reescribir el cliente; exigia mirar la respuesta que ya se estaba guardando entera.

    Se prefiere `user_visible_ttft_ms` sobre `service_ttft_ms` y `engine_ttft_ms` a
    proposito: es el unico de los tres que incluye todo lo que el usuario espera. Los
    otros dos miden tramos internos y son mas chicos por construccion.

    `0` significa que el proveedor no lo informo, y eso NO es un TTFT de cero: se separa
    en el analisis, como todo lo ausente.
    """
    lc = raw_usage.get("latency_checkpoint") or {}
    for clave in ("user_visible_ttft_ms", "service_ttft_ms", "engine_ttft_ms"):
        v = lc.get(clave)
        if v:
            return int(v)
    return 0


@dataclass
class Usage:
    """Lo que UNA llamada al modelo consumió, desglosado por lo que se cobra distinto.

    NO ES UN TOTAL, Y NO PUEDE SERLO. Entrada y salida se facturan entre 4 y 8 veces
    distinto, y los paradigmas se diferencian justo en esa proporción: un brazo que lee
    mucho y responde poco no se puede comparar con uno que hace lo inverso si los dos
    reportan un número solo.

    TRES DISTINCIONES QUE PARECEN SUTILES Y NINGUNA LO ES:

      `provider_cached_tokens`  entrada que el PROVEEDOR sirvió de su caché. Distinto de
                                `cached_calls`, que es NUESTRO caché de disco: aquél evita
                                la llamada entera, éste la abarata
      `reasoning_tokens`        se facturan como SALIDA y no aparecen en el contenido. Sin
                                separarlos, `completion_tokens` mezcla lo que el modelo
                                gastó PENSANDO con lo que gastó RESPONDIENDO — y en los
                                `5.6` esa fracción no la controla nadie de este lado
      `first_ttft_ms`           el tiempo al primer token de la PRIMERA llamada es lo que
                                alguien espera; el total es otra cosa

    `merge` acumula: un paradigma arma su `Usage` a medida que avanza y lo devuelve con la
    respuesta, así que si revienta, la contabilidad muere con él — por eso los contadores
    que tienen que sobrevivir viven en la superficie y no acá.
    """

    prompt_tokens: int = 0
    # TOKENS DE ENTRADA QUE EL PROVEEDOR SIRVIO DE SU CACHE. Distinto de `cached_calls`,
    # que es NUESTRO cache de disco: aquel evita la llamada entera, este la abarata.
    #
    # No se registraba, y por eso `X-4b` no se podia contestar con datos: el cache del
    # endpoint esta encendido por defecto —no hay directiva que mandar— asi que la unica
    # pregunta era si pegaba, y no habia con que mirarlo.
    provider_cached_tokens: int = 0
    # TOKENS DE RAZONAMIENTO, que se facturan como SALIDA y no aparecen en el contenido.
    # Sin separarlos, `completion_tokens` mezcla lo que el modelo decidio gastar PENSANDO
    # con lo que gasto RESPONDIENDO — y en los `5.6` esa fraccion no la controla nadie de
    # este lado, asi que es presupuesto que decide el modelo.
    reasoning_tokens: int = 0
    # TIEMPO AL PRIMER TOKEN. Dos numeros distintos y los dos importan:
    #
    #   first    el de la PRIMERA llamada de la celda. Es lo que alguien espera antes de
    #            ver nada, y es el numero que una interfaz con SSE muestra
    #   total    la suma sobre todas las llamadas. En un bucle de herramientas cada vuelta
    #            vuelve a esperar el primer token, asi que esto es espera acumulada real
    #
    # Sumar el primero seria un sinsentido y quedarse solo con el total esconderia la
    # experiencia. Por eso son dos campos y no uno.
    first_ttft_ms: int = 0
    ttft_ms_total: int = 0
    completion_tokens: int = 0
    calls: int = 0
    cached_calls: int = 0
    wall_seconds: float = 0.0
    # EL DESGLOSE POR MODELO. Cuando una ejecucion rutea `luna` para lo barato y `terra`
    # para una decision compleja, **los tokens dejan de ser una unidad**: uno de `terra`
    # cuesta 10x uno de `luna` en entrada y 10x en salida, y por encima de 272k de prompt
    # los dos saltan a tarifa larga. Sumarlos en un solo entero produce un numero que no
    # se puede convertir a plata ni comparar con nada.
    #
    # `{modelo: {"prompt": n, "completion": n, "calls": n}}`. Vacio significa **un solo
    # modelo** —el regimen medido hasta hoy— y ahi `prompt_tokens`/`completion_tokens`
    # alcanzan. No se rellena con el nombre del modelo por defecto a proposito: "no
    # ruteado" y "ruteado a uno solo" son cosas distintas, y un default las confundiria.
    by_model: dict[str, dict[str, int]] = dc_field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def charge(self, model: str, prompt: int, completion: int) -> None:
        """Atribuye un gasto a un modelo. Lo llama el cliente que sabe cual corrio."""
        if not model:
            return
        celda = self.by_model.setdefault(
            model, {"prompt": 0, "completion": 0, "calls": 0})
        celda["prompt"] += prompt
        celda["completion"] += completion
        celda["calls"] += 1

    def merge(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.provider_cached_tokens += other.provider_cached_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.ttft_ms_total += other.ttft_ms_total
        # EL PRIMERO GANA, y no se suma ni se promedia: es el de la primera llamada de la
        # celda. `0` significa que todavia no hubo ninguna, que se distingue de un TTFT
        # de cero — el proveedor nunca devuelve cero para una llamada real.
        if not self.first_ttft_ms:
            self.first_ttft_ms = other.first_ttft_ms
        self.completion_tokens += other.completion_tokens
        self.calls += other.calls
        self.cached_calls += other.cached_calls
        self.wall_seconds += other.wall_seconds
        for modelo, celda in other.by_model.items():
            mio = self.by_model.setdefault(
                modelo, {"prompt": 0, "completion": 0, "calls": 0})
            for k, v in celda.items():
                mio[k] = mio.get(k, 0) + v

    def as_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "provider_cached_tokens": self.provider_cached_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "first_ttft_ms": self.first_ttft_ms,
            "ttft_ms_total": self.ttft_ms_total,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
            "cached_calls": self.cached_calls,
            "wall_seconds": round(self.wall_seconds, 3),
        }


@dataclass
class Completion:
    """La respuesta del modelo, normalizada, venga de la red o del caché.

    `from_cache` NO ES UN DETALLE DE IMPLEMENTACIÓN: un acierto de caché reporta el
    `Usage` de la llamada ORIGINAL, que es lo correcto para medir el paradigma y lo
    equivocado para saber si una corrida gastó. Lo que separa «se pagó» de «se replayó»
    es `calls - cached_calls`, y una guarda que mirara tokens habría reventado sobre todo
    rellenado sano.

    `model_version` viene del proveedor y puede diferir del deployment pedido: el
    deployment es dónde se llamó, la versión es qué respondió. Guardar las dos es lo que
    permite notar que un endpoint se actualizó abajo.
    """

    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    model_version: str = ""
    from_cache: bool = False


class LLMClient:
    """EL CLIENTE DEL MODELO: una llamada, su caché, su reintento y su traza.

    ES EL ÚNICO LUGAR POR DONDE SALE UNA LLAMADA, y de ahí salen casi todas sus
    responsabilidades.

    EL CACHÉ ES DIRECCIONADO POR CONTENIDO, y la clave incluye la HUELLA —modelo, versión
    de api, esfuerzo de razonamiento, seed y max—. Eso no es una optimización: es lo que
    hace que un replay de la réplica `i` devuelva la réplica `i` y no otra muestra, y que
    dos decodificaciones distintas no puedan compartir entrada ni por accidente. Cuando se
    sacó `temperature` del payload hubo que sacarlo de la huella **en el mismo movimiento**:
    dejarlo vivo en uno solo habría hecho que dos corridas a temperaturas distintas
    compartieran clave.

    EL MODO SELLADO (`sealed`) NO LLAMA A NADIE: un miss es un error, no una llamada. Y
    distingue dos hechos que confundirlos vuelve indiagnosticable un replay fallido — que
    la entrada **nunca estuvo**, o que estaba y estaba **rota**. El primero puede ser una
    huella mal reconstruida; el segundo es daño en el disco.

    LA RESTRICCIÓN QUE GOBIERNA TODO EL BANCO vive acá: en la familia `5.6`, Chat
    Completions **no admite `tools` junto con `reasoning_effort` distinto de `none`**, y
    falla incluso sin mandarlo, porque esos modelos default a `medium`. Todo paradigma de
    este catálogo es un bucle de herramientas, así que hay dos caminos: la Responses API, o
    `none` declarado. **No se fuerza desde acá**: sería arreglar un 400 escondiendo que el
    modelo corre SIN RAZONAR, y eso cambia lo que se mide. Tiene que ser una elección de la
    corrida, que entra a la huella y queda en cada fila.

    LA TRAZA POR LLAMADA (`trace_to`) es opcional y **va acá y no en el bucle**: el bucle
    compartido es 1 de los 27 sitios que llaman al modelo, así que enganchar en el cliente
    los cubre a todos —planificación, verify, replan, síntesis, la extracción del guard,
    los sub-agentes— y ninguno se puede olvidar de instrumentarse. No toca la fila, ni la
    huella, ni la clave de caché.
    """

    def __init__(self, settings: Settings, sealed: bool = False) -> None:
        self._settings = settings
        self._sealed = sealed
        # Claves cuya entrada existia y estaba rota. Se separan de las que nunca
        # estuvieron porque son diagnosticos distintos con arreglos distintos.
        self._corrupt: set[str] = set()
        # Namespaced by account: a deployment name is not a model identity, and the
        # keys themselves do not carry the endpoint (see Settings._account_tag).
        self._cache_dir: Path = settings.cache_dir / settings.account_tag()
        self._url = (
            f"{settings.endpoint}/openai/deployments/{settings.chat_deployment}"
            f"/chat/completions?api-version={settings.api_version}"
        )

    @property
    def fingerprint(self) -> str:
        """The decode identity, for anything that memoises model output of its own."""
        return self._settings.fingerprint()

    @property
    def cache_root(self) -> Path:
        """This account's cache namespace. Anything else memoised from model output
        belongs under here too, for the same reason the completions do."""
        return self._cache_dir

    def sealed_view(self) -> "LLMClient":
        """El mismo cliente, sellado: un miss de cache LEVANTA en vez de llamar en vivo.

        POR QUE UNA VISTA Y NO UN FLAG QUE SE PRENDE. Mutar `self._sealed` sellaria al
        cliente para todos los que lo comparten — el pool devuelve el MISMO objeto por
        modelo, asi que sellar para un request A3 dejaria sellado el de todos los que
        vengan despues. Un sellado que se contagia es peor que no sellar: el sintoma
        aparece en un request que no lo pidio.

        La vista comparte el cache y el namespace porque son los mismos: lo unico que
        cambia es que un miss deja de ser una llamada.

        Y si ya esta sellado se devuelve a si mismo — sellar dos veces es lo mismo que
        sellar una, y construir otro objeto solo agregaria una identidad mas que igualar.
        """
        if self._sealed:
            return self
        return LLMClient(self._settings, sealed=True)

    # -- cache -------------------------------------------------------------

    def _key(self, payload: dict[str, Any]) -> str:
        blob = json.dumps(
            {"fp": self._settings.fingerprint(), "payload": payload},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        # Shard by prefix: a flat directory with 100k entries is slow to list on NTFS.
        shard = self._cache_dir / key[:2]
        shard.mkdir(parents=True, exist_ok=True)
        return shard / f"{key}.json"

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # A truncated entry (crash mid-write, before writes were atomic) must be
            # a MISS, not a poisoned key: left in place, it turned every future run —
            # resumed and sealed included — into a paradigm failure at this key.
            #
            # PERO NO EN SILENCIO. Borrar una entrada ya pagada y seguir como si nada
            # esconde dos cosas distintas y caras: en vivo, que se va a volver a pagar
            # esa llamada; sellado, que "esto no se puede replayar" — que es la misma
            # conclusion que produce un replay con los ajustes equivocados, y ya sabemos
            # cuanto cuesta no poder distinguirlas (R-1).
            self._corrupt.add(key)
            print(f"  [aviso] entrada de cache corrupta, se borra y cuenta como miss: "
                  f"{path.name} ({type(exc).__name__}). En vivo se vuelve a pagar; "
                  f"sellado va a fallar en esta clave.")
            path.unlink(missing_ok=True)
            return None

    def _write_cache(self, key: str, record: dict[str, Any]) -> None:
        write_atomic(
            self._cache_path(key),
            json.dumps(record, ensure_ascii=False, indent=2),
        )

    # -- completion --------------------------------------------------------

    # LA TRAZA POR LLAMADA, y hasta hoy no habia ninguna. La fila agrega la CELDA
    # entera: dice `calls=17` y `cost_tokens=234.341` y **no cual llamada costo que**.
    # Con el costo creciendo como el cuadrado de las vueltas —la conversacion se
    # reenvia entera cada turno— ese es exactamente el numero que hace falta y no
    # estaba.
    #
    # VA EN EL CLIENTE Y NO EN EL BUCLE, a proposito: el bucle compartido es UN sitio
    # de 27 que llaman al modelo. Enganchar aca cubre los 27 —planificacion, verify,
    # replan, sintesis, la extraccion del guard, los sub-agentes— y ninguno se puede
    # olvidar de instrumentarse.
    #
    # NO ES UN SDK NI UNA DEPENDENCIA. El banco es sin framework por diseno: un
    # `.jsonl` es la traza, se lee con las mismas herramientas que el resto del
    # registro, y no agrega una libreria al instrumento que mide.
    _trace_sink: Any = None
    _trace_ctx: dict[str, Any] = {}

    def trace_to(self, path: Any, **contexto: Any) -> None:
        """Escribir una linea por llamada a `path`. `contexto` va en cada linea."""
        self._trace_sink = path
        self._trace_ctx = contexto

    def _trace(self, messages, tools, completion, from_cache: bool) -> None:
        if self._trace_sink is None:
            return
        u = completion.usage
        ventana = sum(len(str(m.get("content") or "")) for m in messages)
        linea = {
            **self._trace_ctx,
            "turno": self._trace_ctx.get("_n", 0),
            "mensajes": len(messages),
            "ventana_chars": ventana,
            "tools_declaradas": len(tools or []),
            "prompt_tokens": getattr(u, "prompt_tokens", 0),
            "completion_tokens": getattr(u, "completion_tokens", 0),
            "from_cache": from_cache,
            "tool_calls": [c["function"]["name"]
                           for c in (completion.tool_calls or [])],
        }
        self._trace_ctx["_n"] = linea["turno"] + 1
        with open(self._trace_sink, "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        seed_override: int | None = None,
    ) -> Completion:
        # `max_completion_tokens`, not `max_tokens`: the GPT-5 family rejects the
        # older parameter outright.
        payload: dict[str, Any] = {
            "messages": messages,
            # Varying the seed is how independent replicate trials are drawn. It is
            # part of the payload, so each trial gets its own cache entry and a
            # replay of trial i returns trial i rather than some other sample.
            "seed": self._settings.seed if seed_override is None else seed_override,
            "max_completion_tokens": max_tokens or self._settings.max_tokens,
        }
        # `temperature` YA NO SE MANDA (2026-08-29). La documentacion de Azure lista a los
        # modelos de razonamiento bajo «Not Supported — `temperature`, `top_p`, ...»: no es
        # que solo acepten 1, es que el parametro no existe para ellos, y `gpt-5.6-luna` y
        # `gpt-5.6-terra` devuelven 400 ante un `temperature: 0.0` explicito.
        #
        # Se saco del payload Y de la huella, en el mismo movimiento. Sacarlo de la huella
        # dejandolo vivo aca habria sido peor que dejarlo: dos corridas a temperaturas
        # distintas compartirian clave de cache y ninguna guarda las separaria.
        if self._settings.reasoning_effort is not None:
            payload["reasoning_effort"] = self._settings.reasoning_effort
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            # Y ACA ESTA LA RESTRICCION QUE GOBIERNA TODO ESTE BANCO. La doc: «The
            # `gpt-5.6` and later models support the Chat Completions API and they support
            # tools, but the Chat Completions API doesn't support the two together. The
            # request fails EVEN WHEN YOU DON'T SEND `reasoning_effort`, because these
            # models default to `medium`. Sending `tools` is enough to trigger the error.»
            #
            # Todo paradigma de este catalogo es un bucle de herramientas sobre Chat
            # Completions, asi que sobre un modelo de razonamiento hay dos caminos: la
            # Responses API, o `reasoning_effort='none'` en cada request que lleve tools.
            #
            # NO SE FUERZA `none` DESDE ACA. Seria arreglar un 400 escondiendo que el
            # modelo corre SIN RAZONAR —«the model then calls tools without reasoning,
            # which loses the planning quality that reasoning provides»—, y eso cambia lo
            # que se esta midiendo. Tiene que ser una eleccion declarada en la corrida, que
            # entra a la huella y queda en cada fila.
            if (self._settings.reasoning_effort not in (None, "none")
                    and _es_de_razonamiento(self._settings.chat_deployment)):
                raise ValueError(
                    f"{self._settings.chat_deployment} no admite `tools` junto con "
                    f"`reasoning_effort={self._settings.reasoning_effort!r}` en Chat "
                    f"Completions. Corre con `MAPO_REASONING_EFFORT=none` —y entonces el "
                    f"modelo llama tools SIN razonar, que es otra medicion y hay que "
                    f"declararlo— o porta el ejecutor a la Responses API."
                )

        key = self._key(payload)
        cached = self._read_cache(key)
        if cached is not None:
            hecho = self._to_completion(cached, from_cache=True)
            self._trace(messages, tools, hecho, from_cache=True)
            return hecho

        if self._sealed:
            # DOS HECHOS DISTINTOS, y confundirlos es lo que hace indiagnosticable a un
            # replay fallido: que la entrada NUNCA estuvo, o que estaba y estaba rota.
            # El primero puede ser ajustes mal reconstruidos —el modelo va en la clave—;
            # el segundo es dano en el disco. El mensaje tiene que decir cual.
            if key in self._corrupt:
                raise SealedCacheMiss(
                    f"La entrada {key} EXISTIA y estaba corrupta: se borro al leerla. "
                    "Esto no es un problema de reconstruccion de ajustes — es dano en "
                    "el cache, y esta celda hay que volver a pagarla sin sellar."
                )
            raise SealedCacheMiss(
                f"Sealed replay requires cache entry {key} which is absent. "
                f"Huella de esta sesion: {self._settings.fingerprint()!r}. Si el registro "
                f"se produjo con OTRO modelo, la clave no puede acertar nunca: el "
                f"deployment va adentro de la huella y la huella adentro de la clave."
            )

        started = time.perf_counter()
        headers = {
            "api-key": self._settings.api_key,
            "Content-Type": "application/json",
        }

        response, attempts = request_with_retry(
            self._url, headers, payload, self._settings.request_timeout
        )

        elapsed = time.perf_counter() - started
        response.raise_for_status()
        body = response.json()

        record = {
            "key": key,
            "fingerprint": self._settings.fingerprint(),
            "model_version": body.get("model", ""),
            "wall_seconds": elapsed,
            # Recorded so a run that limped through rate limiting can be told apart
            # from one that did not.
            "attempts": attempts,
            "body": body,
        }
        self._write_cache(key, record)
        hecho = self._to_completion(record, from_cache=False)
        self._trace(messages, tools, hecho, from_cache=False)
        return hecho

    def _to_completion(self, record: dict[str, Any], from_cache: bool) -> Completion:
        body = record["body"]
        choice = body["choices"][0]
        message = choice["message"]
        raw_usage = body.get("usage", {})

        return Completion(
            text=message.get("content") or "",
            tool_calls=message.get("tool_calls") or [],
            usage=Usage(
                prompt_tokens=raw_usage.get("prompt_tokens", 0),
                completion_tokens=raw_usage.get("completion_tokens", 0),
                # `prompt_tokens_details` puede faltar entero —depende del modelo y de la
                # version de API— y ahi 0 significa «el proveedor no lo informa», que no
                # es «no pego». Se separa en el analisis, no aca.
                provider_cached_tokens=int(
                    (raw_usage.get("prompt_tokens_details") or {}).get(
                        "cached_tokens", 0
                    ) or 0
                ),
                reasoning_tokens=int(
                    (raw_usage.get("completion_tokens_details") or {}).get(
                        "reasoning_tokens", 0
                    ) or 0
                ),
                # `user_visible_ttft_ms` viene en CADA respuesta, incluidas las cacheadas:
                # el cuerpo entero se guarda. Asi que esto se puede rellenar sobre el
                # registro ya pagado sin gastar un token.
                #
                # UN ACIERTO DE CACHE NO TIENE TTFT. Sirviendo del disco el tiempo real es
                # cero, y el numero guardado es el de la llamada ORIGINAL — que sigue
                # siendo el TTFT de esa respuesta, y es lo que interesa del modelo. Se
                # conserva, y `cached_calls` dice cuantas filas lo tienen de segunda mano.
                first_ttft_ms=_ttft(raw_usage),
                ttft_ms_total=_ttft(raw_usage),
                calls=1,
                cached_calls=1 if from_cache else 0,
                # A cache hit costs no wall time; charging the original latency would
                # make a replay look as slow as the live run and distort latency stats.
                wall_seconds=0.0 if from_cache else record.get("wall_seconds", 0.0),
                # EL DESGLOSE POR MODELO SIEMPRE, aunque haya uno solo. Es el cliente el
                # unico que sabe cual deployment corrio esta llamada, y si no lo estampa
                # aca no lo sabe nadie mas: aguas abajo solo llegan enteros sumados. Con un
                # solo modelo el desglose es redundante y no molesta; con dos, es la unica
                # forma de convertir la fila a plata.
                by_model={
                    self._settings.chat_deployment: {
                        "prompt": raw_usage.get("prompt_tokens", 0),
                        "completion": raw_usage.get("completion_tokens", 0),
                        "calls": 1,
                    }
                } if self._settings.chat_deployment else {},
            ),
            model_version=record.get("model_version", ""),
            from_cache=from_cache,
        )


class SeededClient:
    """A view of an LLMClient that pins every call to one seed.

    Replicate trials need a different seed per trial, but threading a seed parameter
    through all seven paradigms would touch code that has nothing to do with sampling.
    Wrapping instead keeps the paradigms unaware that trials exist, which is also the
    honest arrangement: a paradigm must not be able to behave differently because it
    knows which trial it is in.
    """

    def __init__(self, client: LLMClient, seed: int) -> None:
        self._client = client
        self._seed = seed
        # Running total for THIS cell. A paradigm builds its own Usage as it goes and
        # returns it with the answer, so when it raises, the accounting dies with it and
        # the error row claims the failure was free. Tokens were spent; theta must not
        # learn that the paradigm "fails cheaply". One wrapper per (task, trial,
        # paradigm) cell makes this the cell's meter, not a global one.
        self.spent = Usage()

    # Forwarded, not reimplemented: a paradigm that memoises model output must land in
    # the same namespace whether it was handed the client or a seeded view of it.
    @property
    def fingerprint(self) -> str:
        return self._client.fingerprint

    @property
    def cache_root(self) -> Path:
        return self._client.cache_root

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        completion = self._client.complete(
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            seed_override=self._seed,
        )
        self.spent.merge(completion.usage)
        return completion
