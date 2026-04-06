"""
Redis-backed cache helpers with graceful degradation when Redis is unavailable.

The client is initialised lazily on first use. If REDIS_URL is empty or Redis
is unreachable, every operation silently no-ops so the app continues to work
without caching.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis_client = None
_redis_unavailable = False  # avoid repeated connection attempts after first failure


def _get_client():
    global _redis_client, _redis_unavailable
    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        from core.config import settings
        if not settings.REDIS_URL:
            return None
        import redis
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client.ping()  # verify connection
        logger.info("Redis cache connected: %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable — caching disabled: %s", exc)
        _redis_unavailable = True
        _redis_client = None
    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception:
        logger.warning("Redis GET failed for key=%s", key, exc_info=True)
        return None


def cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.set(key, json.dumps(value), ex=ttl)
    except Exception:
        logger.warning("Redis SET failed for key=%s", key, exc_info=True)


def cache_delete(key: str) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        logger.warning("Redis DELETE failed for key=%s", key, exc_info=True)


def annual_cache_key(user_id: int, year: int) -> str:
    return f"annual:{user_id}:{year}"


def invalidate_annual_cache(user_id: int, year: int) -> None:
    """Delete the cached annual overview for a given user and year."""
    cache_delete(annual_cache_key(user_id, year))
