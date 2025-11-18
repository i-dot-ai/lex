"""Rate limiting and monitoring middleware."""

import time

from fastapi import Request, Response

from backend.core.cache import cache
from backend.core.config import RATE_LIMIT_PER_HOUR, RATE_LIMIT_PER_MINUTE
from backend.monitoring import monitoring


def get_client_ip(request: Request) -> str:
    """Extract client IP considering proxy headers."""
    # Check X-Forwarded-For header first (Azure Container Apps)
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Fallback to X-Real-IP
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip

    # Last resort: direct connection IP
    return getattr(request.client, "host", "unknown")


def add_rate_limit_headers(response, minute_count: int, hour_count: int) -> None:
    """Add rate limiting headers to response."""
    response.headers["X-RateLimit-Limit-Minute"] = str(RATE_LIMIT_PER_MINUTE)
    response.headers["X-RateLimit-Remaining-Minute"] = str(
        max(0, RATE_LIMIT_PER_MINUTE - minute_count)
    )
    response.headers["X-RateLimit-Limit-Hour"] = str(RATE_LIMIT_PER_HOUR)
    response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, RATE_LIMIT_PER_HOUR - hour_count))


def track_request_safely(
    request: Request, response, duration: float, minute_count: int, hour_count: int
) -> None:
    """Track request with safe error handling for monitoring."""
    try:
        # Track rate limiting events if approaching limits
        if minute_count > RATE_LIMIT_PER_MINUTE * 0.8:  # 80% threshold
            monitoring.track_rate_limit_event(
                request,
                "minute",
                minute_count,
                RATE_LIMIT_PER_MINUTE,
                exceeded=(minute_count > RATE_LIMIT_PER_MINUTE),
            )

        if hour_count > RATE_LIMIT_PER_HOUR * 0.8:  # 80% threshold
            monitoring.track_rate_limit_event(
                request,
                "hour",
                hour_count,
                RATE_LIMIT_PER_HOUR,
                exceeded=(hour_count > RATE_LIMIT_PER_HOUR),
            )

        # Track monitoring events based on path
        if request.url.path == "/":
            monitoring.track_page_view(request, "home")
        elif request.url.path == "/api/docs":
            monitoring.track_page_view(request, "api_docs")
        elif request.url.path == "/api/redoc":
            monitoring.track_page_view(request, "redoc")
        elif request.url.path not in ["/", "/api/docs", "/api/redoc", "/api/openapi.json"]:
            query_params = dict(request.query_params) if request.query_params else None
            monitoring.track_api_usage(
                request, request.url.path, duration, response.status_code, query_params
            )
    except Exception as e:
        # If monitoring fails, don't break the request - just log
        print(f"Monitoring error (non-critical): {e}")


async def monitoring_and_rate_limit_middleware(request: Request, call_next):
    """Combined monitoring and rate limiting middleware with proper exception handling."""
    start_time = time.time()
    minute_count = 0
    hour_count = 0

    try:
        # Skip rate limiting for health checks
        if request.url.path in ["/healthcheck", "/health"]:
            response = await call_next(request)
            return response

        # Get client IP and check rate limits
        client_ip = get_client_ip(request)
        minute_key = f"rate_limit:minute:{client_ip}"
        hour_key = f"rate_limit:hour:{client_ip}"

        minute_count = cache.increment_with_ttl(minute_key, 60)
        hour_count = cache.increment_with_ttl(hour_key, 3600)

        # Check limits and return early with proper headers
        if minute_count > RATE_LIMIT_PER_MINUTE or hour_count > RATE_LIMIT_PER_HOUR:
            limit_type = "minute" if minute_count > RATE_LIMIT_PER_MINUTE else "hour"
            limit_value = (
                RATE_LIMIT_PER_MINUTE
                if minute_count > RATE_LIMIT_PER_MINUTE
                else RATE_LIMIT_PER_HOUR
            )

            # Create 429 response with headers
            response = Response(
                content=f"Rate limit exceeded: {limit_value} requests per {limit_type}",
                status_code=429,
                media_type="text/plain",
            )
            add_rate_limit_headers(response, minute_count, hour_count)
            return response

        # Process the request
        response = await call_next(request)
        duration = time.time() - start_time

        # Add monitoring and headers safely
        track_request_safely(request, response, duration, minute_count, hour_count)
        add_rate_limit_headers(response, minute_count, hour_count)

        return response

    except Exception as e:
        # Only catch unexpected errors, not HTTP responses
        try:
            monitoring.track_error(request, e, request.url.path)
        except Exception:
            # If monitoring fails, don't break the original error
            pass
        raise
