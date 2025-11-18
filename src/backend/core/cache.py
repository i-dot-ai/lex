"""Smart caching with Redis fallback and decorators."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Optional

import redis

from backend.core.config import DEFAULT_CACHE_TTL, REDIS_PASSWORD, REDIS_URL


class SmartCache:
    """Smart cache that works with Redis or in-memory fallback."""

    def __init__(self):
        self.redis_client = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.use_redis = False

        # Try to connect to Redis
        if REDIS_URL:
            try:
                # Create Redis client with password if provided
                if REDIS_PASSWORD:
                    self.redis_client = redis.from_url(
                        REDIS_URL, password=REDIS_PASSWORD, decode_responses=True
                    )
                else:
                    self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)

                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                logging.info("Connected to Redis for caching and rate limiting")
            except Exception as e:
                logging.warning(f"Failed to connect to Redis, using in-memory cache: {e}")
        else:
            logging.info("No Redis URL configured, using in-memory cache")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if self.use_redis:
            try:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            except Exception as e:
                logging.error(f"Redis get error: {e}")
                return None
        else:
            # Check memory cache with TTL
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if datetime.now() < entry["expires"]:
                    return entry["value"]
                else:
                    del self.memory_cache[key]
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL."""
        if self.use_redis:
            try:
                self.redis_client.setex(key, ttl, json.dumps(value))
                return True
            except Exception as e:
                logging.error(f"Redis set error: {e}")
                return False
        else:
            # Store in memory with expiration
            self.memory_cache[key] = {
                "value": value,
                "expires": datetime.now() + timedelta(seconds=ttl),
            }
            # Simple cleanup: remove expired entries occasionally
            if len(self.memory_cache) > 1000:
                now = datetime.now()
                expired_keys = [k for k, v in self.memory_cache.items() if now >= v["expires"]]
                for k in expired_keys:
                    del self.memory_cache[k]
            return True

    def increment_with_ttl(self, key: str, ttl: int = 60) -> int:
        """Increment counter with TTL for rate limiting."""
        if self.use_redis:
            try:
                # Use Redis pipeline for atomic increment with TTL
                pipe = self.redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, ttl)
                result = pipe.execute()
                return result[0]  # Return the incremented value
            except Exception as e:
                logging.error(f"Redis increment error: {e}")
                return 0
        else:
            # In-memory rate limiting
            now = datetime.now()
            if key not in self.memory_cache:
                self.memory_cache[key] = {"value": 1, "expires": now + timedelta(seconds=ttl)}
                return 1
            else:
                entry = self.memory_cache[key]
                if now < entry["expires"]:
                    entry["value"] += 1
                    return entry["value"]
                else:
                    # Reset expired counter
                    self.memory_cache[key] = {"value": 1, "expires": now + timedelta(seconds=ttl)}
                    return 1

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

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.use_redis:
            try:
                # Get Redis info if available
                info = self.redis_client.info()
                return {
                    "backend": "redis",
                    "connected": True,
                    "used_memory": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients"),
                }
            except Exception as e:
                return {"backend": "redis", "connected": False, "error": str(e)}
        else:
            return {
                "backend": "memory",
                "size": len(self.memory_cache),
                "connected": True,
            }


# Global cache instance
cache = SmartCache()

# Export decorator for backward compatibility
cached_search = cache.cached_decorator()
