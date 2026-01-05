"""Error handling utilities for FastAPI routers."""

import traceback
from functools import wraps
from typing import Callable, TypeVar

from fastapi import HTTPException

T = TypeVar("T")


def handle_errors(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that catches exceptions and converts them to HTTPException with detailed error info.

    Preserves HTTPExceptions (for auth, validation, etc.) but wraps unexpected exceptions
    with traceback details for debugging.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise FastAPI HTTPExceptions unchanged (e.g., 404, 401, etc.)
            raise
        except Exception as e:
            # Wrap unexpected errors with detailed context
            error_detail = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
            }
            raise HTTPException(status_code=500, detail=error_detail)

    return wrapper
