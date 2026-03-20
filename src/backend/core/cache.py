"""Smart caching with Redis fallback and decorators."""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

import redis

from backend.core.config import (
    DEFAULT_CACHE_TTL,
    RATE_LIMIT_MEMORY_MAX_ENTRIES,
    REDIS_PASSWORD,
    REDIS_URL,
)

# Lua script for atomic fixed-window rate limiting.
# Only sets TTL on key creation (count == 1), giving a true fixed window
# rather than a sliding window that resets on every request.
_INCR_WITH_FIXED_TTL = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class SmartCache:
    """Smart cache that works with Redis or in-memory fallback.

    When Redis is unavailable, automatically falls back to in-memory storage
    and periodically attempts reconnection.
    """

    def __init__(self):
        self.redis_client = None
        self.memory_cache: dict[str, dict[str, Any]] = {}
        self.use_redis = False
        self._incr_script = None
        self._redis_last_error_time: float = 0.0
        self._redis_reconnect_interval: float = 30.0

        # Try to connect to Redis
        if REDIS_URL:
            try:
                if REDIS_PASSWORD:
                    self.redis_client = redis.from_url(
                        REDIS_URL, password=REDIS_PASSWORD, decode_responses=True
                    )
                else:
                    self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)

                # Test connection
                self.redis_client.ping()
                self._incr_script = self.redis_client.register_script(_INCR_WITH_FIXED_TTL)
                self.use_redis = True
                logging.info("Connected to Redis for caching and rate limiting")
            except Exception as e:
                logging.warning(f"Failed to connect to Redis, using in-memory cache: {e}")
        else:
            logging.info("No Redis URL configured, using in-memory cache")

    def _check_redis_health(self) -> bool:
        """Attempt to restore Redis connection if previously failed."""
        if self.use_redis:
            return True
        if self.redis_client is None:
            return False
        now = time.time()
        if now - self._redis_last_error_time < self._redis_reconnect_interval:
            return False
        try:
            self.redis_client.ping()
            self._incr_script = self.redis_client.register_script(_INCR_WITH_FIXED_TTL)
            self.use_redis = True
            logging.info("Redis connection restored")
            return True
        except Exception:
            self._redis_last_error_time = now
            return False

    def _handle_redis_failure(self, error: Exception, context: str) -> None:
        """Mark Redis as unavailable and log the failure."""
        logging.warning(f"Redis {context} error, falling back to memory: {error}")
        self.use_redis = False
        self._redis_last_error_time = time.time()

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        self._check_redis_health()
        if self.use_redis:
            try:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            except Exception as e:
                self._handle_redis_failure(e, "get")

        # In-memory fallback
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if datetime.now() < entry["expires"]:
                return entry["value"]
            else:
                del self.memory_cache[key]
        return None

    def _make_serializable(self, value: Any) -> Any:
        """Convert value to JSON-serializable format, handling Pydantic models."""
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {k: self._make_serializable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._make_serializable(item) for item in value]
        return value

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL."""
        self._check_redis_health()
        if self.use_redis:
            try:
                serializable_value = self._make_serializable(value)
                self.redis_client.setex(key, ttl, json.dumps(serializable_value, default=str))
                return True
            except Exception as e:
                self._handle_redis_failure(e, "set")

        # In-memory fallback
        self.memory_cache[key] = {
            "value": value,
            "expires": datetime.now() + timedelta(seconds=ttl),
        }
        if len(self.memory_cache) > RATE_LIMIT_MEMORY_MAX_ENTRIES:
            self._evict_expired()
        return True

    def _evict_expired(self) -> None:
        """Remove expired entries, then oldest live entries if still over limit."""
        now = datetime.now()
        expired_keys = [k for k, v in self.memory_cache.items() if now >= v["expires"]]
        for k in expired_keys:
            del self.memory_cache[k]

        # If still over limit after removing expired, evict oldest by expiry time
        if len(self.memory_cache) > RATE_LIMIT_MEMORY_MAX_ENTRIES:
            sorted_entries = sorted(
                self.memory_cache.items(),
                key=lambda item: item[1]["expires"],
            )
            entries_to_remove = len(self.memory_cache) - RATE_LIMIT_MEMORY_MAX_ENTRIES
            for k, _ in sorted_entries[:entries_to_remove]:
                del self.memory_cache[k]

    def increment_with_ttl(self, key: str, ttl: int = 60) -> int:
        """Increment counter with TTL for rate limiting.

        Uses a Lua script on Redis for atomic fixed-window counting.
        Falls through to in-memory on Redis failure.
        """
        self._check_redis_health()
        if self.use_redis:
            try:
                return self._incr_script(keys=[key], args=[ttl])
            except Exception as e:
                self._handle_redis_failure(e, "increment")

        # In-memory fallback
        now = datetime.now()
        if key not in self.memory_cache:
            self.memory_cache[key] = {"value": 1, "expires": now + timedelta(seconds=ttl)}
            count = 1
        else:
            entry = self.memory_cache[key]
            if now < entry["expires"]:
                entry["value"] += 1
                count = entry["value"]
            else:
                self.memory_cache[key] = {"value": 1, "expires": now + timedelta(seconds=ttl)}
                count = 1

        if len(self.memory_cache) > RATE_LIMIT_MEMORY_MAX_ENTRIES:
            self._evict_expired()

        return count

    def cache_key_from_args(self, func_name: str, **kwargs) -> str:
        """Generate cache key from function name and arguments."""
        sorted_kwargs = json.dumps(kwargs, sort_keys=True, default=str)
        key_str = f"api_cache:{func_name}:{sorted_kwargs}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def cached_decorator(self, ttl: int = DEFAULT_CACHE_TTL):
        """Decorator for caching function results with configurable TTL."""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key from function and input model
                if args and hasattr(args[0], "model_dump"):
                    cache_key = self.cache_key_from_args(func.__name__, **args[0].model_dump())
                else:
                    return await func(*args, **kwargs)

                # Check cache
                cached = self.get(cache_key)
                if cached is not None:
                    logging.debug(f"Cache hit for {func.__name__}")
                    return cached

                # Cache miss - execute function
                result = await func(*args, **kwargs)
                self.set(cache_key, result, ttl)

                return result

            return wrapper

        return decorator

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        self._check_redis_health()
        if self.use_redis:
            try:
                info = self.redis_client.info()
                return {
                    "backend": "redis",
                    "connected": True,
                    "used_memory": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients"),
                }
            except Exception as e:
                self._handle_redis_failure(e, "stats")

        return {
            "backend": "memory",
            "size": len(self.memory_cache),
            "connected": True,
        }


# Global cache instance
cache = SmartCache()

# Export decorator for backward compatibility
cached_search = cache.cached_decorator()
