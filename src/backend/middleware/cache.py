"""Request-level caching for API responses."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class RequestCache:
    """In-memory cache with TTL for API responses."""

    def __init__(self, ttl_seconds: int = 28800):  # 8 hours default
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl = ttl_seconds

    def _cache_key(self, func_name: str, **kwargs) -> str:
        """Generate cache key from function name and arguments."""
        sorted_kwargs = json.dumps(kwargs, sort_keys=True, default=str)
        key_str = f"{func_name}:{sorted_kwargs}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        """Retrieve from cache if not expired."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if datetime.now() < expiry:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        """Store in cache with TTL."""
        expiry = datetime.now() + timedelta(seconds=self._ttl)
        self._cache[key] = (value, expiry)

    def clear_expired(self):
        """Remove expired entries."""
        now = datetime.now()
        expired = [k for k, (_, exp) in self._cache.items() if now >= exp]
        for k in expired:
            del self._cache[k]

    def size(self) -> int:
        """Return number of cached items."""
        return len(self._cache)


# Global cache instance
_request_cache = RequestCache(ttl_seconds=28800)  # 8 hours


def cached_search(func):
    """Decorator for caching search results."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Generate cache key from function and input model
        if args and hasattr(args[0], "model_dump"):
            cache_key = _request_cache._cache_key(
                func.__name__, **args[0].model_dump()
            )
        else:
            return await func(*args, **kwargs)

        # Check cache
        cached = _request_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for {func.__name__}")
            return cached

        # Cache miss - execute function
        result = await func(*args, **kwargs)
        _request_cache.set(cache_key, result)

        return result

    return wrapper


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return {
        "size": _request_cache.size(),
        "ttl_seconds": _request_cache._ttl,
        "ttl_hours": _request_cache._ttl / 3600,
    }
