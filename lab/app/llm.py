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
from dataclasses import dataclass, field
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


class SealedCacheMiss(RuntimeError):
    """Raised when a sealed replay needs a completion that is not in the cache.

    In sealed mode a miss is a hard error and never a live call: silently going to
    the network would mean the "replay" produced fresh, unaudited content.
    """


@dataclass
class Usage:
    prompt_tokens: int = 0
    # TOKENS DE ENTRADA QUE EL PROVEEDOR SIRVIO DE SU CACHE. Distinto de `cached_calls`,
    # que es NUESTRO cache de disco: aquel evita la llamada entera, este la abarata.
    #
    # No se registraba, y por eso `X-4b` no se podia contestar con datos: el cache del
    # endpoint esta encendido por defecto —no hay directiva que mandar— asi que la unica
    # pregunta era si pegaba, y no habia con que mirarlo.
    provider_cached_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    cached_calls: int = 0
    wall_seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def merge(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.provider_cached_tokens += other.provider_cached_tokens
        self.completion_tokens += other.completion_tokens
        self.calls += other.calls
        self.cached_calls += other.cached_calls
        self.wall_seconds += other.wall_seconds

    def as_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "provider_cached_tokens": self.provider_cached_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
            "cached_calls": self.cached_calls,
            "wall_seconds": round(self.wall_seconds, 3),
        }


@dataclass
class Completion:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    model_version: str = ""
    from_cache: bool = False


class LLMClient:
    """Content-addressed Azure OpenAI client."""

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
        # gpt-5-chat accepts ONLY the default temperature and 400s on an explicit 0,
        # so the parameter is omitted rather than forced. Omission is recorded in the
        # fingerprint, because a run at the model default is not the same experiment
        # as a run at temperature 0 and the two must never be pooled.
        if self._settings.temperature is not None:
            payload["temperature"] = self._settings.temperature
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        key = self._key(payload)
        cached = self._read_cache(key)
        if cached is not None:
            return self._to_completion(cached, from_cache=True)

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
        return self._to_completion(record, from_cache=False)

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
                calls=1,
                cached_calls=1 if from_cache else 0,
                # A cache hit costs no wall time; charging the original latency would
                # make a replay look as slow as the live run and distort latency stats.
                wall_seconds=0.0 if from_cache else record.get("wall_seconds", 0.0),
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
