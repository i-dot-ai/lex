import logging
import os
import time
from typing import Any, Dict, Optional, Type, Union

import requests
from diskcache import FanoutCache
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from lex.core.exceptions import RateLimitException
from lex.core.rate_limiter import AdaptiveRateLimiter, CircuitBreaker

logger = logging.getLogger(__name__)


class HttpClient:
    """A robust HTTP client with exponential backoff, retry logic, and persistent disk caching."""

    def __init__(
        self,
        max_retries: int = 30,
        initial_delay: float = 1.0,
        max_delay: float = 600.0,
        timeout: Optional[Union[float, tuple]] = 30,
        session: Optional[requests.Session] = None,
        retry_exceptions: Optional[tuple[Type[Exception], ...]] = None,
        enable_cache: bool = True,
        cache_dir: Optional[str] = None,
        cache_size_limit: int = 1_000_000_000,  # 1GB default
        cache_ttl: int = 28800,  # 8 hours in seconds
    ):
        """
        Initialize the HTTP client.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            timeout: Default timeout for requests
            session: Optional requests.Session to use
            retry_exceptions: Tuple of exceptions to retry on. Defaults to common HTTP errors
            enable_cache: Whether to enable response caching
            cache_dir: Directory for cache storage. Defaults to ~/.cache/lex/http
            cache_size_limit: Maximum cache size in bytes
            cache_ttl: Time to live for cached items in seconds
        """
        self.timeout = timeout
        self.session = session or requests.Session()
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self.cache_size_limit = cache_size_limit

        # Default exceptions to retry on
        self.retry_exceptions = retry_exceptions or (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            RateLimitException,  # Important: retry on rate limits
        )

        # Create the retry decorator with configured parameters
        self._retry_decorator = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=self.initial_delay,
                min=self.initial_delay,
                max=self.max_delay,
            ),
            retry=retry_if_exception_type(self.retry_exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )

        # Create persistent cache if enabled
        if self.enable_cache:
            if cache_dir is None:
                # Check if running in container with mounted volume
                if os.path.exists("/app/data"):
                    cache_dir = "/app/data/cache/http"
                else:
                    # Local development - use project data directory
                    cache_dir = os.path.join(os.getcwd(), "data", "cache", "http")

            # Ensure cache directory exists
            os.makedirs(cache_dir, exist_ok=True)

            # Use FanoutCache for better concurrency (shards across multiple SQLite files)
            # timeout=60 prevents immediate failures on lock contention
            self._cache = FanoutCache(
                directory=cache_dir,
                size_limit=cache_size_limit,
                timeout=60,  # Wait up to 60s for locks instead of failing immediately
                shards=8,  # Distribute across 8 SQLite files for better concurrency
            )
            logger.debug(f"FanoutCache initialized at {cache_dir} with 8 shards")

        # Initialize rate limiter and circuit breaker
        self.rate_limiter = AdaptiveRateLimiter()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=10, recovery_timeout=300, expected_exception=RateLimitException
        )

    def _make_request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Make request with retry logic."""
        response = self.session.request(method=method, url=url, timeout=self.timeout, **kwargs)

        # Check for rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    retry_after = int(retry_after)
                except ValueError:
                    retry_after = None

            self.rate_limiter.record_rate_limit(retry_after)

            logger.warning(
                f"Rate limited: {url}",
                extra={
                    "event_type": "rate_limit",
                    "url": url,
                    "retry_after": retry_after,
                    "current_delay": self.rate_limiter.get_current_delay(),
                    "status_code": 429,
                },
            )

            # Convert to RateLimitException so circuit breaker can track it
            raise RateLimitException(f"Rate limited on {url}", retry_after)

        response.raise_for_status()
        return response

    def _make_request_with_circuit_breaker(
        self, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        """Wrap request with circuit breaker and rate limiting."""
        # Apply adaptive delay
        delay = self.rate_limiter.get_current_delay()
        if delay > 0:
            logger.debug(f"Applying rate limit delay: {delay}s")
            time.sleep(delay)

        try:
            # Use circuit breaker to protect against cascading failures
            response = self.circuit_breaker.call(
                self._retry_decorator(self._make_request), method, url, **kwargs
            )
            self.rate_limiter.record_success()
            return response
        except RateLimitException:
            # Re-raise rate limit exceptions
            raise
        except Exception as e:
            # Log other exceptions but re-raise
            logger.error(f"Request failed: {e}")
            raise

    def _get_cache_key(self, method: str, url: str, **kwargs: Any) -> str:
        """Generate a cache key from the request parameters."""
        # Sort kwargs to ensure consistent keys
        sorted_kwargs = sorted(
            [(k, v) for k, v in kwargs.items() if k not in ["data", "json", "files"]]
        )
        return f"{method}:{url}:{str(sorted_kwargs)}"

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """
        Make an HTTP request with retry logic and optional caching.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            **kwargs: Additional arguments to pass to requests

        Returns:
            requests.Response: The response object

        Raises:
            requests.exceptions.RequestException: If all retry attempts fail
            RateLimitException: If rate limited and circuit breaker is open
        """
        # Only cache GET requests
        if not self.enable_cache or method != "GET":
            # Clear cache for non-GET methods that modify data
            if self.enable_cache and method in ["POST", "PUT", "PATCH", "DELETE"]:
                self.clear_cache()
            return self._make_request_with_circuit_breaker(method, url, **kwargs)

        # For GET requests with cache enabled
        cache_key = self._get_cache_key(method, url, **kwargs)

        # Check cache
        try:
            cached_response = self._cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache hit for {url}")
                return cached_response
        except Exception as e:
            # Auto-recreate cache if corrupted
            if "database disk image is malformed" in str(e):
                logger.warning(f"Cache corrupted, recreating: {e}")
                self._recreate_cache()
            else:
                logger.warning(f"Cache read error for {url}: {e}. Continuing without cache.")
            # Continue without cache on read errors

        # Cache miss - make request
        response = self._make_request_with_circuit_breaker(method, url, **kwargs)

        # Store in cache
        try:
            self._cache.set(cache_key, response, expire=self.cache_ttl)
            logger.debug(f"Cached response for {url}")
        except Exception as e:
            # Auto-recreate cache if corrupted
            if "database disk image is malformed" in str(e):
                logger.warning(f"Cache corrupted, recreating: {e}")
                self._recreate_cache()
            else:
                logger.warning(
                    f"Cache write error for {url}: {e}. Response returned without caching."
                )

        return response

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Make a GET request with caching."""
        return self.request("GET", url, **kwargs)

    def clear_cache(self) -> None:
        """Clear the entire cache."""
        if self.enable_cache:
            try:
                self._cache.clear()
                logger.debug("Cache cleared")
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}. Attempting to recreate cache.")
                self._recreate_cache()

    def _recreate_cache(self) -> None:
        """Recreate the cache directory if corrupted."""
        if self.enable_cache and hasattr(self, "_cache"):
            try:
                # Close existing cache
                self._cache.close()
            except Exception:
                pass

            # Get cache directory
            cache_dir = self._cache.directory

            # Remove corrupted cache files
            import shutil

            try:
                shutil.rmtree(cache_dir)
                logger.info(f"Removed corrupted cache directory: {cache_dir}")
            except Exception as e:
                logger.error(f"Failed to remove cache directory: {e}")

            # Recreate cache
            os.makedirs(cache_dir, exist_ok=True)
            self._cache = FanoutCache(
                directory=cache_dir,
                size_limit=self.cache_size_limit,
                timeout=60,
                shards=8,
            )
            logger.info("FanoutCache recreated successfully")

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current cache state.

        Returns:
            Dict containing cache statistics
        """
        if not self.enable_cache:
            return {"enabled": False}

        return {
            "enabled": True,
            "size": self._cache.size,
            "size_limit": self._cache.size_limit,
            "directory": self._cache.directory,
            "ttl": self.cache_ttl,
        }

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        """Make a POST request."""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> requests.Response:
        """Make a PUT request."""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> requests.Response:
        """Make a DELETE request."""
        return self.request("DELETE", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> requests.Response:
        """Make a HEAD request."""
        return self.request("HEAD", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> requests.Response:
        """Make an OPTIONS request."""
        return self.request("OPTIONS", url, **kwargs)
