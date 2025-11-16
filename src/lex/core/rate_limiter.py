"""Rate limiting and circuit breaker implementations for HTTP requests."""

import logging
import time
from collections import deque
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar('T')

logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts delay based on server responses.

    Note: legislation.gov.uk enforces a limit of 1500 requests per 5-minute window.
    Default min_delay of 0.2s allows ~5 req/sec per process, staying well under the limit.
    """

    def __init__(
        self,
        min_delay: float = 0.2,
        max_delay: float = 300.0,
        success_reduction_factor: float = 0.95,
        failure_increase_factor: float = 2.0,
    ):
        """
        Initialize the adaptive rate limiter.

        Args:
            min_delay: Minimum delay between requests in seconds (default 0.2s = 5 req/sec max)
            max_delay: Maximum delay between requests in seconds (default 300s = 5 minutes)
            success_reduction_factor: Factor to reduce delay after success (0-1)
            failure_increase_factor: Factor to increase delay after rate limit
        """
        self.successful_requests: deque[float] = deque(maxlen=10000)  # Track last 10k requests
        self.rate_limit_events: deque[Dict[str, Any]] = deque(maxlen=100)  # Track 429/436 responses
        self.current_delay = min_delay  # Start with minimum delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.success_reduction_factor = success_reduction_factor
        self.failure_increase_factor = failure_increase_factor

    def record_success(self) -> None:
        """Record a successful request and potentially reduce delay."""
        self.successful_requests.append(time.time())

        # Gradually reduce delay after sustained success
        if len(self.successful_requests) > 100 and self.current_delay > self.min_delay:
            self.current_delay *= self.success_reduction_factor
            self.current_delay = max(self.current_delay, self.min_delay)

    def record_rate_limit(self, retry_after: Optional[int] = None) -> None:
        """Record a rate limit event and increase delay."""
        event = {"time": time.time(), "retry_after": retry_after}
        self.rate_limit_events.append(event)

        # If we have a retry_after header, use it
        if retry_after:
            self.current_delay = float(retry_after)
        else:
            # Exponentially increase delay
            new_delay = self.current_delay * self.failure_increase_factor + 0.5
            self.current_delay = min(new_delay, self.max_delay)

        logger.info(
            f"Rate limit recorded. New delay: {self.current_delay}s",
            extra={
                "rate_limiter_delay": self.current_delay,
                "retry_after": retry_after,
                "recent_rate_limits": len(self.rate_limit_events),
            },
        )

    def get_current_delay(self) -> float:
        """Get the current delay to apply before next request."""
        return self.current_delay

    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics."""
        recent_success_count = sum(
            1 for t in self.successful_requests if time.time() - t < 3600
        )  # Last hour
        recent_limit_count = sum(
            1 for e in self.rate_limit_events if time.time() - e["time"] < 3600
        )  # Last hour

        return {
            "current_delay": self.current_delay,
            "recent_success_count": recent_success_count,
            "recent_rate_limit_count": recent_limit_count,
            "total_requests": len(self.successful_requests),
        }


class CircuitBreaker:
    """Circuit breaker pattern to prevent cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 10,
        recovery_timeout: int = 300,
        expected_exception: type = Exception,
    ):
        """
        Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type that triggers the breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Call the protected function with circuit breaker logic.

        Raises:
            Exception: If circuit is open
        """
        if self.state == "open":
            if self.last_failure_time and time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                logger.info("Circuit breaker entering half-open state")
            else:
                raise Exception(f"Circuit breaker is open. Retry after {self.recovery_timeout}s")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == "half-open":
            self.state = "closed"
            logger.info("Circuit breaker closed after successful recovery")
        self.failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures",
                extra={
                    "circuit_state": self.state,
                    "failure_count": self.failure_count,
                    "recovery_timeout": self.recovery_timeout,
                },
            )

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "can_attempt": self.state != "open"
            or (
                self.last_failure_time
                and time.time() - self.last_failure_time > self.recovery_timeout
            ),
        }
