"""Error handling utilities for FastAPI routers."""

import logging
import uuid
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

from fastapi import HTTPException

T = TypeVar("T")

logger = logging.getLogger(__name__)


def handle_errors(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that catches unexpected exceptions and returns sanitised 500 responses.

    Preserves HTTPExceptions (for auth, validation, etc.) but wraps unexpected exceptions
    with a correlation ID for server-side debugging.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            error_id = uuid.uuid4().hex[:8]
            logger.error(
                f"Unhandled error [{error_id}]: {type(e).__name__}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail={"error": "Internal server error", "error_id": error_id},
            )

    return wrapper
