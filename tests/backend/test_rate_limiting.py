"""Tests for rate limiting and SmartCache."""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.core.cache import SmartCache


def _make_memory_cache():
    """Create a SmartCache that uses in-memory storage (no Redis)."""
    with patch.dict("os.environ", {"REDIS_URL": ""}, clear=False):
        with patch("backend.core.cache.REDIS_URL", None):
            return SmartCache()


class TestIncrementWithTtl:
    def test_returns_incrementing_count(self):
        cache = _make_memory_cache()
        assert cache.increment_with_ttl("key", ttl=60) == 1
        assert cache.increment_with_ttl("key", ttl=60) == 2
        assert cache.increment_with_ttl("key", ttl=60) == 3

    def test_resets_after_expiry(self):
        cache = _make_memory_cache()
        assert cache.increment_with_ttl("key", ttl=1) == 1
        assert cache.increment_with_ttl("key", ttl=1) == 2
        time.sleep(1.1)
        assert cache.increment_with_ttl("key", ttl=1) == 1

    def test_independent_keys(self):
        cache = _make_memory_cache()
        assert cache.increment_with_ttl("key_a", ttl=60) == 1
        assert cache.increment_with_ttl("key_b", ttl=60) == 1
        assert cache.increment_with_ttl("key_a", ttl=60) == 2
        assert cache.increment_with_ttl("key_b", ttl=60) == 2

    def test_memory_cleanup_on_overflow(self):
        cache = _make_memory_cache()

        # Fill with expired entries
        past = datetime.now() - timedelta(seconds=10)
        for i in range(200):
            cache.memory_cache[f"expired_{i}"] = {"value": 1, "expires": past}

        # Set max entries low for testing
        with patch("backend.core.cache.RATE_LIMIT_MEMORY_MAX_ENTRIES", 100):
            cache.increment_with_ttl("trigger_cleanup", ttl=60)

        # Expired entries should have been evicted
        expired_remaining = [k for k in cache.memory_cache if k.startswith("expired_")]
        assert len(expired_remaining) == 0
        assert "trigger_cleanup" in cache.memory_cache


class TestRedisFailover:
    def test_redis_failure_falls_through_to_memory(self):
        cache = _make_memory_cache()

        # Simulate a cache that was connected to Redis
        mock_client = MagicMock()
        cache.redis_client = mock_client
        cache.use_redis = True

        mock_script = MagicMock(side_effect=ConnectionError("Redis down"))
        cache._incr_script = mock_script

        # Should fall through to memory and return valid count, not 0
        result = cache.increment_with_ttl("key", ttl=60)
        assert result == 1
        assert cache.use_redis is False

        # Subsequent calls should use memory directly
        result = cache.increment_with_ttl("key", ttl=60)
        assert result == 2

    def test_redis_reconnection_after_failure(self):
        cache = _make_memory_cache()

        mock_client = MagicMock()
        cache.redis_client = mock_client
        cache.use_redis = False
        cache._redis_last_error_time = time.time() - 60  # Well past reconnect interval

        # ping succeeds — should restore Redis
        mock_client.ping.return_value = True
        assert cache._check_redis_health() is True
        assert cache.use_redis is True

    def test_redis_reconnection_skipped_within_interval(self):
        cache = _make_memory_cache()

        mock_client = MagicMock()
        cache.redis_client = mock_client
        cache.use_redis = False
        cache._redis_last_error_time = time.time()  # Just failed

        # Should not attempt reconnection yet
        assert cache._check_redis_health() is False
        mock_client.ping.assert_not_called()

    def test_failed_reconnection_updates_error_time(self):
        cache = _make_memory_cache()

        mock_client = MagicMock()
        mock_client.ping.side_effect = ConnectionError("Still down")
        cache.redis_client = mock_client
        cache.use_redis = False
        cache._redis_last_error_time = time.time() - 60

        assert cache._check_redis_health() is False
        assert cache.use_redis is False
        assert cache._redis_last_error_time > time.time() - 2

    def test_get_falls_through_on_redis_error(self):
        cache = _make_memory_cache()

        # Pre-populate memory cache
        cache.memory_cache["key"] = {
            "value": "hello",
            "expires": datetime.now() + timedelta(seconds=60),
        }

        # Simulate Redis connected but failing
        mock_client = MagicMock()
        mock_client.get.side_effect = ConnectionError("Redis down")
        cache.redis_client = mock_client
        cache.use_redis = True

        result = cache.get("key")
        assert result == "hello"
        assert cache.use_redis is False

    def test_set_falls_through_on_redis_error(self):
        cache = _make_memory_cache()

        mock_client = MagicMock()
        mock_client.setex.side_effect = ConnectionError("Redis down")
        cache.redis_client = mock_client
        cache.use_redis = True

        result = cache.set("key", "value", ttl=60)
        assert result is True
        assert cache.use_redis is False
        assert cache.memory_cache["key"]["value"] == "value"


class TestMiddlewareRateLimiting:
    def _create_test_app(self):
        """Create a minimal FastAPI app with rate limiting middleware."""
        from backend.core.middleware import monitoring_and_rate_limit_middleware

        app = FastAPI()

        @app.get("/healthcheck")
        async def healthcheck():
            return {"status": "healthy"}

        @app.get("/test")
        async def test_endpoint():
            return {"result": "ok"}

        app.middleware("http")(monitoring_and_rate_limit_middleware)
        return app

    @patch("backend.core.middleware.monitoring")
    @patch("backend.core.middleware.RATE_LIMIT_PER_MINUTE", 3)
    @patch("backend.core.middleware.RATE_LIMIT_PER_HOUR", 100)
    @patch("backend.core.middleware.cache")
    def test_returns_429_when_exceeded(self, mock_cache, mock_monitoring):
        call_count = 0

        def increment_side_effect(key, ttl):
            nonlocal call_count
            if "minute" in key:
                call_count += 1
                return call_count
            return 1

        mock_cache.increment_with_ttl.side_effect = increment_side_effect

        app = self._create_test_app()
        client = TestClient(app)

        # First 3 requests should succeed
        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200

        # 4th request should be rate limited
        response = client.get("/test")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.text

    @patch("backend.core.middleware.monitoring")
    @patch("backend.core.middleware.RATE_LIMIT_PER_MINUTE", 100)
    @patch("backend.core.middleware.RATE_LIMIT_PER_HOUR", 3)
    @patch("backend.core.middleware.cache")
    def test_returns_429_when_hourly_limit_exceeded(self, mock_cache, mock_monitoring):
        hourly_call_count = 0

        def increment_side_effect(key, ttl):
            nonlocal hourly_call_count
            if "hour" in key:
                hourly_call_count += 1
                return hourly_call_count
            return 1

        mock_cache.increment_with_ttl.side_effect = increment_side_effect

        app = self._create_test_app()
        client = TestClient(app)

        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429

    @patch("backend.core.middleware.monitoring")
    @patch("backend.core.middleware.cache")
    def test_healthcheck_bypasses_rate_limiting(self, mock_cache, mock_monitoring):
        app = self._create_test_app()
        client = TestClient(app)

        response = client.get("/healthcheck")
        assert response.status_code == 200
        mock_cache.increment_with_ttl.assert_not_called()

    @patch("backend.core.middleware.monitoring")
    @patch("backend.core.middleware.RATE_LIMIT_PER_MINUTE", 100)
    @patch("backend.core.middleware.RATE_LIMIT_PER_HOUR", 1000)
    @patch("backend.core.middleware.cache")
    def test_rate_limit_headers_present(self, mock_cache, mock_monitoring):
        mock_cache.increment_with_ttl.return_value = 1

        app = self._create_test_app()
        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Remaining-Minute" in response.headers
        assert "X-RateLimit-Limit-Hour" in response.headers
        assert "X-RateLimit-Remaining-Hour" in response.headers
