"""Environment configuration.

Every value is read from the environment with NO default. A missing variable is a
hard failure at import time, not a silent fallback to something plausible.
"""

from __future__ import annotations

import os
import hashlib
import re

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable is missing or empty: {name}")
    return value


MODEL_DEFAULT = "model_default"


def _require_temperature(name: str) -> float | None:
    """Temperature, or None meaning "do not send the parameter at all".

    Not a hidden default: the literal string `model_default` must be set explicitly.
    Some deployments (gpt-5-chat) reject any explicit temperature, so the choice has
    to be expressible, and it has to appear in the fingerprint.
    """
    raw = _require(name)
    if raw.strip() == MODEL_DEFAULT:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a float or the literal '{MODEL_DEFAULT}', got {raw!r}"
        ) from exc


def _require_int(name: str) -> int:
    raw = _require(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an int, got {raw!r}") from exc


def _require_dir(name: str) -> Path:
    path = Path(_require(name))
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class Settings:
    """Immutable run configuration.

    Frozen on purpose: the whole point of the experiment is that a given
    (corpus, paradigm, settings) triple is replayable. A mutable settings object
    would let a run drift halfway through and silently invalidate the numbers.
    """

    endpoint: str
    # repr=False on both keys: a dataclass prints every field, and a Settings object
    # ends up in tracebacks, logs and notebook cells. A secret that is one exception
    # away from stdout is a secret already leaked.
    api_key: str = field(repr=False)
    api_version: str
    chat_deployment: str
    embedding_deployment: str
    # Embeddings can live on a DIFFERENT account than chat: a second chat model on a
    # fresh account still needs the one embedding deployment that exists and is cached.
    embedding_endpoint: str
    embedding_api_key: str = field(repr=False)
    temperature: float | None
    seed: int
    max_tokens: int
    request_timeout: int
    cache_dir: Path
    results_dir: Path
    corpus_dir: Path
    # DEPLOYMENTS DEL CATALOGO, por nombre LOGICO (`fast`, `deep`). Vacio significa un
    # solo modelo —el de `chat_deployment`— que es el regimen en el que se midio todo.
    #
    # POR QUE LA INDIRECCION. El catalogo (`app/models.py`) declara CAPACIDAD y ARANCEL,
    # que son propiedades del modelo; el deployment es DONDE esta desplegado, que es
    # infraestructura. Fundirlas obligaria a tocar la capa de decision cada vez que
    # alguien redespliega, y la capa de decision es lo que no se toca.
    model_deployments: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            endpoint=_require("AZURE_OPENAI_ENDPOINT").rstrip("/"),
            api_key=_require("AZURE_OPENAI_API_KEY"),
            api_version=_require("AZURE_OPENAI_API_VERSION"),
            chat_deployment=_require("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            # `MAPO_MODEL_DEPLOYMENTS="fast=gpt-5.4-nano,deep=gpt-5.6-terra"`. Opcional a
            # proposito: sin ella el sistema corre con un modelo, que es como se midio
            # todo hasta hoy, y eso NO es un default silencioso — es el regimen medido.
            model_deployments=_optional_deployments("MAPO_MODEL_DEPLOYMENTS"),
            embedding_deployment=_require("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            embedding_endpoint=_require("AZURE_OPENAI_EMBEDDING_ENDPOINT").rstrip("/"),
            embedding_api_key=_require("AZURE_OPENAI_EMBEDDING_API_KEY"),
            temperature=_require_temperature("MAPO_TEMPERATURE"),
            seed=_require_int("MAPO_SEED"),
            max_tokens=_require_int("MAPO_MAX_TOKENS"),
            request_timeout=_require_int("MAPO_REQUEST_TIMEOUT"),
            cache_dir=_require_dir("MAPO_CACHE_DIR"),
            results_dir=_require_dir("MAPO_RESULTS_DIR"),
            corpus_dir=_require_dir("MAPO_CORPUS_DIR"),
        )

    def account_tag(self) -> str:
        """Cache namespace for the chat account."""
        return _account_tag(self.endpoint)

    def embedding_account_tag(self) -> str:
        """Cache namespace for the embedding account (it may be a different one)."""
        return _account_tag(self.embedding_endpoint)

    def fingerprint(self) -> str:
        """Identity of the decode configuration.

        Goes into every cache key and every result row, so a result can never be
        confused with one produced under different decoding.
        """
        temp = MODEL_DEFAULT if self.temperature is None else self.temperature
        return (
            f"{self.chat_deployment}|{self.api_version}"
            f"|t={temp}|seed={self.seed}|max={self.max_tokens}"
        )


def _optional_deployments(name: str) -> dict[str, str]:
    """`fast=deployment,deep=otro`. Vacio si la variable no esta.

    SE PARSEA CON VOCABULARIO CERRADO. Las claves tienen que estar en el catalogo de
    modelos, asi que esto no es leer prosa: es leer pares de una lista enumerada. Una
    clave que no esta levanta en `ModelPool`, no aca — un solo lugar que decide que es un
    modelo valido.
    """
    crudo = os.environ.get(name, "").strip()
    if not crudo:
        return {}
    out: dict[str, str] = {}
    for par in crudo.split(","):
        if "=" not in par:
            raise ValueError(
                f"{name}: {par!r} no tiene la forma `logico=deployment`. Se levanta en "
                f"vez de ignorarlo: un deployment que se pierde en el parseo hace que el "
                f"sistema corra con menos modelos de los que alguien configuro."
            )
        logico, deployment = par.split("=", 1)
        logico, deployment = logico.strip(), deployment.strip()
        if not logico or not deployment:
            raise ValueError(f"{name}: {par!r} tiene una mitad vacia.")
        if logico in out:
            raise ValueError(
                f"{name}: {logico!r} aparece dos veces. Quedarse con el ultimo elegiria "
                f"un modelo por orden de escritura, que nadie decidio."
            )
        out[logico] = deployment
    return out


def _account_tag(endpoint: str) -> str:
    """A cache namespace for one account.

    THE COLLISION. Cache keys are content-addressed over the payload and the DECODE
    fingerprint -- deployment name, api-version, temperature, seed, max tokens. None of
    that is the ACCOUNT. Two resources can each serve a deployment called `gpt-5-nano`,
    and "same name" is not "same model": whoever owns the other resource decides what is
    behind that name. Pointed at a second account, the client would have served the first
    account's completions as if they were this one's, silently.

    WHY A DIRECTORY AND NOT THE FINGERPRINT. Putting the host INSIDE the hash would have
    closed the same hole and thrown away every entry ever paid for -- the record does not
    keep the request payload, so no migration can re-derive the new keys, and a sealed
    replay of the frozen grid would stop being replayable. Namespacing the directory
    gives the same guarantee (two accounts can never read each other's entries) while the
    keys, and therefore the replays, stay exactly as they were.

    The tag keeps the host readable, because a human reading the cache tree is one of the
    ways this gets audited, and appends a digest of the full endpoint so two hosts that
    sanitise to the same string still cannot meet.
    """
    host = endpoint.split("://")[-1].split("/")[0].lower()
    safe = re.sub(r"[^a-z0-9]+", "-", host).strip("-")[:40] or "endpoint"
    digest = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:8]
    return f"{safe}-{digest}"
