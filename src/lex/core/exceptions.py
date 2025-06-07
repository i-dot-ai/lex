class LexParsingError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class RateLimitException(Exception):
    """Raised when API rate limit is hit."""
    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after
