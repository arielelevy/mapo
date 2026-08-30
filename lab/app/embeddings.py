"""Content-addressed embedding client.

Embeddings are what make a production-grade retriever possible here without giving up
replayability. A fixed text under a fixed model yields a stable vector, so the vector is
cached exactly as completions are, and after the first pass retrieval becomes a
deterministic local computation over cached vectors — no network, no variance, no cost.

The scale is small enough that this is not an optimisation but a one-off: a corpus is
some dozens of units, embedded once.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .fsio import write_atomic
from .llm import SealedCacheMiss, request_with_retry


class EmbeddingClient:
    """LOS VECTORES, cacheados por CONTENIDO y en su propia cuenta.

    Vive en un recurso distinto del modelo de chat (`AZURE_OPENAI_EMBEDDING_*`), con su
    propia configuración, y eso no es un detalle de despliegue: el caché lleva namespace
    por cuenta, así que dos endpoints no pueden servirse vectores el uno del otro.

    EL CACHÉ ES POR CONTENIDO, no por unidad ni por corpus. Un texto que aparece en dos
    corpus se embebe una vez, y regenerar un corpus con el mismo material no vuelve a
    pagar. Después de la primera pasada, la fusión híbrida es aritmética local: eso es lo
    que hace que la calidad de recuperación pueda ser un **dial controlado** y no otra
    fuente de costo.
    """

    def __init__(self, settings: Settings, deployment: str, sealed: bool = False) -> None:
        self._settings = settings
        self._deployment = deployment
        self._sealed = sealed
        # Same namespacing as the chat cache, and by the EMBEDDING endpoint, which is
        # allowed to be a different account than chat.
        self._dir: Path = (
            settings.cache_dir / settings.embedding_account_tag() / "embeddings"
        )
        self._dir.mkdir(parents=True, exist_ok=True)
        self._url = (
            f"{settings.embedding_endpoint}/openai/deployments/{deployment}"
            f"/embeddings?api-version={settings.api_version}"
        )
        # Process-local memo, so a retriever scoring 60 units does not re-read 60 files
        # for every query.
        self._memo: dict[str, list[float]] = {}

    def _key(self, text: str) -> str:
        blob = f"{self._deployment}|{self._settings.api_version}|{text}"
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        shard = self._dir / key[:2]
        shard.mkdir(parents=True, exist_ok=True)
        return shard / f"{key}.json"

    def embed(self, text: str) -> list[float]:
        key = self._key(text)
        if key in self._memo:
            return self._memo[key]

        path = self._path(key)
        if path.exists():
            try:
                vector = json.loads(path.read_text(encoding="utf-8"))["vector"]
                self._memo[key] = vector
                return vector
            except (json.JSONDecodeError, KeyError, OSError):
                # A truncated entry is a miss, not a poisoned key (see fsio).
                path.unlink(missing_ok=True)

        if self._sealed:
            raise SealedCacheMiss(
                f"Sealed replay needs embedding {key} which is not cached. "
                "Run unsealed once to populate it."
            )

        # Same retry as the chat client, because it is the same failure. This used to
        # be a separate copy and the copy was worse: it had no ceiling on Retry-After,
        # so a long hint slept for as long as the server named and looked like a hang.
        response, _ = request_with_retry(
            self._url,
            {
                "api-key": self._settings.embedding_api_key,
                "Content-Type": "application/json",
            },
            {"input": text},
            self._settings.request_timeout,
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
        write_atomic(
            path, json.dumps({"deployment": self._deployment, "vector": vector})
        )
        self._memo[key] = vector
        return vector

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def describe(self) -> dict[str, Any]:
        return {"deployment": self._deployment, "cached": len(self._memo)}


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
