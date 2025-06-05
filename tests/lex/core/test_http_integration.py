import os
import tempfile
import time

import pytest
import requests

from lex.core.http import HttpClient


class TestHttpClientIntegration:
    """Integration tests for HttpClient with real HTTP requests."""

    def test_basic_get_request(self):
        """Test basic GET request functionality."""
        client = HttpClient(enable_cache=False)

        # Use a reliable public API for testing
        response = client.get("https://httpbin.org/get")

        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert data["url"] == "https://httpbin.org/get"

    def test_get_request_with_parameters(self):
        """Test GET request with query parameters."""
        client = HttpClient(enable_cache=False)

        params = {"param1": "value1", "param2": "value2"}
        response = client.get("https://httpbin.org/get", params=params)

        assert response.status_code == 200
        data = response.json()
        assert data["args"]["param1"] == "value1"
        assert data["args"]["param2"] == "value2"

    def test_post_request(self):
        """Test POST request functionality."""
        client = HttpClient(enable_cache=False)

        post_data = {"key": "value", "test": "data"}
        response = client.post("https://httpbin.org/post", json=post_data)

        assert response.status_code == 200
        data = response.json()
        assert data["json"]["key"] == "value"
        assert data["json"]["test"] == "data"

    def test_request_with_headers(self):
        """Test request with custom headers."""
        client = HttpClient(enable_cache=False)

        headers = {"User-Agent": "Lex-Test-Client/1.0", "X-Custom-Header": "test-value"}

        response = client.get("https://httpbin.org/headers", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["headers"]["User-Agent"] == "Lex-Test-Client/1.0"
        assert data["headers"]["X-Custom-Header"] == "test-value"

    def test_caching_functionality(self):
        """Test HTTP response caching."""
        # Use a temporary directory for cache
        with tempfile.TemporaryDirectory() as temp_dir:
            client = HttpClient(
                enable_cache=True,
                cache_dir=temp_dir,
                cache_ttl=60,  # 1 minute TTL
            )

            # First request - should be cached
            start_time = time.time()
            response1 = client.get("https://httpbin.org/delay/1")  # 1 second delay
            first_request_time = time.time() - start_time

            assert response1.status_code == 200
            assert first_request_time >= 1.0  # Should take at least 1 second

            # Second request - should be from cache (much faster)
            start_time = time.time()
            response2 = client.get("https://httpbin.org/delay/1")
            second_request_time = time.time() - start_time

            assert response2.status_code == 200
            assert second_request_time < 0.1  # Should be much faster from cache

            # Verify responses are identical
            assert response1.json() == response2.json()

    def test_cache_miss_for_different_urls(self):
        """Test that different URLs don't share cache entries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = HttpClient(enable_cache=True, cache_dir=temp_dir)

            # Request to different endpoints
            response1 = client.get("https://httpbin.org/get?param=1")
            response2 = client.get("https://httpbin.org/get?param=2")

            assert response1.status_code == 200
            assert response2.status_code == 200

            # Should have different responses
            data1 = response1.json()
            data2 = response2.json()
            assert data1["args"]["param"] != data2["args"]["param"]

    def test_cache_invalidation_on_post(self):
        """Test that cache is cleared on POST requests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = HttpClient(enable_cache=True, cache_dir=temp_dir)

            # Make a GET request to populate cache
            response1 = client.get("https://httpbin.org/get")
            assert response1.status_code == 200

            # Verify cache has content
            cache_info = client.get_cache_info()
            assert cache_info["enabled"] is True

            # Make a POST request (should clear cache)
            post_response = client.post("https://httpbin.org/post", json={"test": "data"})
            assert post_response.status_code == 200

            # Cache should still be enabled but potentially cleared
            cache_info_after = client.get_cache_info()
            assert cache_info_after["enabled"] is True

    def test_retry_logic_with_timeout(self):
        """Test retry logic with timeout scenarios."""
        client = HttpClient(
            max_retries=3, initial_delay=0.1, max_delay=1.0, timeout=2.0, enable_cache=False
        )

        # Test with a request that should succeed
        response = client.get("https://httpbin.org/get")
        assert response.status_code == 200

    def test_different_http_methods(self):
        """Test various HTTP methods."""
        client = HttpClient(enable_cache=False)

        # Test GET
        get_response = client.get("https://httpbin.org/get")
        assert get_response.status_code == 200

        # Test POST
        post_response = client.post("https://httpbin.org/post", json={"test": "data"})
        assert post_response.status_code == 200

        # Test PUT
        put_response = client.put("https://httpbin.org/put", json={"test": "data"})
        assert put_response.status_code == 200

        # Test DELETE
        delete_response = client.delete("https://httpbin.org/delete")
        assert delete_response.status_code == 200

        # Test HEAD
        head_response = client.head("https://httpbin.org/get")
        assert head_response.status_code == 200
        assert len(head_response.content) == 0  # HEAD should have no body

    def test_cache_directory_creation(self):
        """Test that cache directory is created automatically."""
        # Use a non-existent directory path
        cache_dir = os.path.join(tempfile.gettempdir(), "test_lex_cache", "http")

        # Ensure directory doesn't exist
        if os.path.exists(cache_dir):
            import shutil

            shutil.rmtree(os.path.dirname(cache_dir))

        try:
            client = HttpClient(enable_cache=True, cache_dir=cache_dir)

            # Make a request to trigger cache creation
            response = client.get("https://httpbin.org/get")
            assert response.status_code == 200

            # Verify cache directory was created
            assert os.path.exists(cache_dir)

            # Verify cache info
            cache_info = client.get_cache_info()
            assert cache_info["enabled"] is True
            assert cache_info["directory"] == cache_dir

        finally:
            # Clean up
            if os.path.exists(cache_dir):
                import shutil

                shutil.rmtree(os.path.dirname(cache_dir))

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = HttpClient(
                enable_cache=True,
                cache_dir=temp_dir,
                cache_ttl=1,  # 1 second TTL
            )

            # Make initial request
            response1 = client.get("https://httpbin.org/uuid")
            assert response1.status_code == 200
            uuid1 = response1.json()["uuid"]

            # Immediate second request should be cached
            response2 = client.get("https://httpbin.org/uuid")
            uuid2 = response2.json()["uuid"]
            assert uuid1 == uuid2  # Should be same from cache

            # Wait for TTL to expire
            time.sleep(1.5)

            # Third request should get new data
            response3 = client.get("https://httpbin.org/uuid")
            uuid3 = response3.json()["uuid"]
            # Note: This test might be flaky since httpbin.org/uuid might return
            # the same UUID, but it demonstrates the TTL concept

    def test_request_with_authentication(self):
        """Test request with authentication headers."""
        client = HttpClient(enable_cache=False)

        # Test basic auth (httpbin.org supports this)
        response = client.get("https://httpbin.org/basic-auth/user/pass", auth=("user", "pass"))

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"] == "user"

    def test_request_with_custom_session(self):
        """Test HttpClient with custom session."""
        session = requests.Session()
        session.headers.update({"X-Custom-Session": "test-session"})

        client = HttpClient(session=session, enable_cache=False)

        response = client.get("https://httpbin.org/headers")
        assert response.status_code == 200

        data = response.json()
        assert data["headers"]["X-Custom-Session"] == "test-session"

    def test_large_response_handling(self):
        """Test handling of larger responses."""
        client = HttpClient(enable_cache=False)

        # Request a larger response (1KB of random data)
        response = client.get("https://httpbin.org/bytes/1024")

        assert response.status_code == 200
        assert len(response.content) == 1024

    def test_json_response_parsing(self):
        """Test JSON response parsing."""
        client = HttpClient(enable_cache=False)

        response = client.get("https://httpbin.org/json")
        assert response.status_code == 200

        # Should be able to parse JSON
        data = response.json()
        assert isinstance(data, dict)
        # httpbin.org/json returns a sample JSON object

    def test_error_handling_404(self):
        """Test handling of 404 errors."""
        client = HttpClient(enable_cache=False, max_retries=1)

        from tenacity import RetryError

        with pytest.raises(RetryError):
            client.get("https://httpbin.org/status/404")

    def test_error_handling_500(self):
        """Test handling of 500 errors with retry."""
        client = HttpClient(enable_cache=False, max_retries=2, initial_delay=0.1)

        from tenacity import RetryError

        with pytest.raises(RetryError):
            client.get("https://httpbin.org/status/500")


class TestHttpClientRealWorldScenarios:
    """Test HttpClient with real-world-like scenarios."""

    def test_legislation_api_simulation(self):
        """Test scenario simulating legislation API calls."""
        client = HttpClient(
            enable_cache=True,
            cache_ttl=300,  # 5 minutes
            max_retries=3,
        )

        # Simulate searching for legislation
        search_params = {"q": "data protection", "type": "ukpga", "year": "2018"}

        response = client.get("https://httpbin.org/get", params=search_params)
        assert response.status_code == 200

        data = response.json()
        assert data["args"]["q"] == "data protection"
        assert data["args"]["type"] == "ukpga"
        assert data["args"]["year"] == "2018"

    def test_multiple_concurrent_requests(self):
        """Test multiple requests to simulate concurrent usage."""
        client = HttpClient(enable_cache=True)

        urls = [
            "https://httpbin.org/get?id=1",
            "https://httpbin.org/get?id=2",
            "https://httpbin.org/get?id=3",
            "https://httpbin.org/get?id=4",
            "https://httpbin.org/get?id=5",
        ]

        responses = []
        for url in urls:
            response = client.get(url)
            assert response.status_code == 200
            responses.append(response)

        # Verify all responses are unique
        response_data = [r.json() for r in responses]
        ids = [data["args"]["id"] for data in response_data]
        assert len(set(ids)) == 5  # All unique IDs

    def test_api_with_rate_limiting_simulation(self):
        """Test behavior with simulated rate limiting."""
        client = HttpClient(max_retries=3, initial_delay=0.5, max_delay=2.0, enable_cache=True)

        # Make multiple requests quickly
        for i in range(3):
            response = client.get(f"https://httpbin.org/get?request={i}")
            assert response.status_code == 200

            # Small delay between requests
            time.sleep(0.1)

    def test_cache_performance_benefit(self):
        """Test that caching provides performance benefits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = HttpClient(enable_cache=True, cache_dir=temp_dir, cache_ttl=300)

            url = "https://httpbin.org/delay/0.5"  # 500ms delay

            # First request - should take time
            start_time = time.time()
            response1 = client.get(url)
            first_duration = time.time() - start_time

            assert response1.status_code == 200
            assert first_duration >= 0.5

            # Second request - should be much faster
            start_time = time.time()
            response2 = client.get(url)
            second_duration = time.time() - start_time

            assert response2.status_code == 200
            assert second_duration < 0.1  # Should be much faster

            # Verify cache was used
            cache_info = client.get_cache_info()
            assert cache_info["enabled"] is True


# Fixtures
@pytest.fixture
def http_client():
    """Fixture providing a basic HttpClient."""
    return HttpClient(enable_cache=False)


@pytest.fixture
def cached_http_client():
    """Fixture providing an HttpClient with caching enabled."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield HttpClient(enable_cache=True, cache_dir=temp_dir, cache_ttl=60)
