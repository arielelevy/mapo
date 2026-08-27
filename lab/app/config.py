"""Environment configuration.

Every value is read from the environment with NO default. A missing variable is a
hard failure at import time, not a silent fallback to something plausible.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
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
    api_key: str
    api_version: str
    chat_deployment: str
    embedding_deployment: str
    # Embeddings can live on a DIFFERENT account than chat: a second chat model on a
    # fresh account still needs the one embedding deployment that exists and is cached.
    embedding_endpoint: str
    embedding_api_key: str
    temperature: float | None
    seed: int
    max_tokens: int
    request_timeout: int
    cache_dir: Path
    results_dir: Path
    corpus_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            endpoint=_require("AZURE_OPENAI_ENDPOINT").rstrip("/"),
            api_key=_require("AZURE_OPENAI_API_KEY"),
            api_version=_require("AZURE_OPENAI_API_VERSION"),
            chat_deployment=_require("AZURE_OPENAI_CHAT_DEPLOYMENT"),
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
