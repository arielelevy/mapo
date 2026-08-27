"""Async Redis cache for the Chat orchestrator pipeline.

Requires a reachable Redis. Raises on startup if unavailable.

Usage:
    value = await cache_get(username, "doc_text", entity_id)
    if value is None:
        value = await expensive_call()
        await cache_set(username, "doc_text", entity_id, value=value)
"""

import hashlib
import json
import logging
from typing import Any

from app.api.v1.common.utils.redis_cache import get_redis_global_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache entry definitions — single source of truth for names + TTLs
# ---------------------------------------------------------------------------

CACHE_ENTRIES = {
    "workspace_filter": {
        "ttl": 300,  # 5 min — workspace permissions from the auth service
        "desc": "Allowed workspace IDs per user (from the auth token)",
    },
}


def _entry(name: str) -> dict:
    """The declared entry for `name`, or a refusal.

    CACHE_ENTRIES called itself the single source of truth for names and TTLs while
    cache_set accepted any name at all and fell back to 300 seconds — so the table
    documented one entry and the code allowed an open set. Unknown names are now a
    programming error, which is what they always were.
    """
    entry = CACHE_ENTRIES.get(name)
    if entry is None:
        raise ValueError(
            f"Unknown cache entry {name!r}. Declare it in CACHE_ENTRIES with a TTL."
        )
    return entry


def _make_key(username: str, name: str, *parts: str) -> str:
    raw = ":".join(str(p) for p in parts)
    h = hashlib.sha256(raw.encode()).hexdigest()
    return f"chat:{username}:{name}:{h}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def cache_get(username: str, name: str, *parts: str) -> Any | None:
    """Get cached value scoped to username. Returns None on miss."""
    if not username:
        raise ValueError("username is required for cache security")
    _entry(name)
    r = get_redis_global_client()
    key = _make_key(username, name, *parts)
    data = await r.get(key)
    if data is not None:
        return json.loads(data)
    return None


async def cache_set(username: str, name: str, *parts: str, value: Any) -> None:
    """Set cached value scoped to username with TTL from CACHE_ENTRIES."""
    if not username:
        raise ValueError("username is required for cache security")
    r = get_redis_global_client()
    ttl = _entry(name)["ttl"]
    key = _make_key(username, name, *parts)
    await r.set(key, json.dumps(value, default=str), ex=ttl)
