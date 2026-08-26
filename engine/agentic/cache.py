"""Async Redis cache for the Chat orchestrator pipeline.

Requires Redis (via kubefwd). Raises on startup if unavailable.

Usage:
    value = await cache_get(username, "doc_text", entity_id)
    if value is None:
        value = await expensive_call()
        await cache_set(username, "doc_text", entity_id, value=value)
"""

import hashlib
import json
import logging
from typing import Any, Optional

from app.api.v1.common.utils.redis_cache import get_redis_global_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache entry definitions — single source of truth for names + TTLs
# ---------------------------------------------------------------------------

CACHE_ENTRIES = {
    "workspace_filter": {
        "ttl": 300,  # 5 min — workspace permissions from Timbr
        "desc": "Allowed workspace IDs per user (from Timbr JWT)",
    },
}


def _make_key(username: str, name: str, *parts: str) -> str:
    raw = ":".join(str(p) for p in parts)
    h = hashlib.sha256(raw.encode()).hexdigest()
    return f"chat:{username}:{name}:{h}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def cache_get(username: str, name: str, *parts: str) -> Optional[Any]:
    """Get cached value scoped to username. Returns None on miss."""
    if not username:
        raise ValueError("username is required for cache security")
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
    entry = CACHE_ENTRIES.get(name, {})
    ttl = entry.get("ttl", 300)
    key = _make_key(username, name, *parts)
    await r.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_ping() -> bool:
    """Check Redis connectivity. Raises if unavailable."""
    r = get_redis_global_client()
    return await r.ping()


def cache_stats() -> dict:
    """Return cache info."""
    r = get_redis_global_client()
    info = r.connection_pool.connection_kwargs
    return {
        "backend": "redis",
        "host": info.get("host", "unknown"),
        "port": info.get("port", 6379),
    }
