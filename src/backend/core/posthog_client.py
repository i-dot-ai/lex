"""PostHog analytics client for server-side event tracking."""

import atexit
import hashlib
import logging

from posthog import Posthog

from backend.core.config import POSTHOG_HOST, POSTHOG_KEY

logger = logging.getLogger(__name__)

_client: Posthog | None = None

if POSTHOG_KEY:
    try:
        _client = Posthog(
            api_key=POSTHOG_KEY,
            host=POSTHOG_HOST or "https://eu.i.posthog.com",
            disable_geoip=True,
        )
        atexit.register(_client.shutdown)
        logger.info("PostHog server-side analytics initialised")
    except Exception as e:
        logger.warning(f"Failed to initialise PostHog: {e}")


def capture_api_event(
    client_ip: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Capture an API request event. Non-blocking, fire-and-forget."""
    if _client is None:
        return
    try:
        _client.capture(
            distinct_id=hashlib.sha256(client_ip.encode()).hexdigest()[:16],
            event="api_request",
            properties={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "duration_ms": round(duration_ms),
                "is_mcp": endpoint.startswith("/mcp"),
                "is_error": status_code >= 400,
            },
        )
    except Exception:
        pass


def shutdown() -> None:
    """Flush and shut down the PostHog client. Call on app shutdown."""
    if _client:
        _client.shutdown()
