from typing import Optional


class LexParsingError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class RateLimitException(Exception):
    """Raised when API rate limit is hit."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class NotFoundError(Exception):
    """Raised when a resource is not found (HTTP 404). Should not be retried."""

    def __init__(self, message: str, url: Optional[str] = None):
        super().__init__(message)
        self.url = url


class ProcessedException(Exception):
    """
    Exception that marks a URL as processed even though parsing failed.

    Use this for recoverable failures where we don't want to retry the URL
    (e.g., PDF documents, corrupted content, unsupported formats).
    """

    def __init__(self, message: str, url: Optional[str] = None):
        super().__init__(message)
        self.url = url
