import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

import requests
from diskcache import Cache
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class HttpClient:
    """A robust HTTP client with exponential backoff, retry logic, and persistent disk caching."""

    def __init__(
        self,
        max_retries: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: Optional[Union[float, tuple]] = 10,
        session: Optional[requests.Session] = None,
        retry_exceptions: Optional[tuple[Type[Exception], ...]] = None,
        enable_cache: bool = True,
        cache_dir: Optional[str] = None,
        cache_size_limit: int = 1_000_000_000,  # 1GB default
        cache_ttl: int = 3600,  # 1 hour in seconds
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

        # Default exceptions to retry on
        self.retry_exceptions = retry_exceptions or (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
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
                # Default to ~/.cache/lex/http
                home_dir = Path.home()
                cache_dir = os.path.join(home_dir, ".cache", "lex", "http")

            # Ensure cache directory exists
            os.makedirs(cache_dir, exist_ok=True)

            self._cache = Cache(
                directory=cache_dir,
                size_limit=cache_size_limit,
            )
            logger.debug(f"Cache initialized at {cache_dir}")

    def _make_request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """
        Internal method that makes the actual request.
        This is decorated with retry logic.
        """
        response = self.session.request(method=method, url=url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response

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
        """
        # Only cache GET requests
        if not self.enable_cache or method != "GET":
            # Clear cache for non-GET methods that modify data
            if self.enable_cache and method in ["POST", "PUT", "PATCH", "DELETE"]:
                self.clear_cache()
            return self._retry_decorator(self._make_request)(method, url, **kwargs)

        # For GET requests with cache enabled
        cache_key = self._get_cache_key(method, url, **kwargs)

        # Check cache
        cached_response = self._cache.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Cache hit for {url}")
            return cached_response

        # Cache miss - make request
        response = self._retry_decorator(self._make_request)(method, url, **kwargs)

        # Store in cache
        self._cache.set(cache_key, response, expire=self.cache_ttl)
        logger.debug(f"Cached response for {url}")

        return response

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Make a GET request with caching."""
        return self.request("GET", url, **kwargs)

    def clear_cache(self) -> None:
        """Clear the entire cache."""
        if self.enable_cache:
            self._cache.clear()
            logger.debug("Cache cleared")

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
