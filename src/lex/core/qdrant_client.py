import asyncio
import functools
import logging
import time

from qdrant_client import AsyncQdrantClient, QdrantClient

from lex.settings import (
    QDRANT_API_KEY,
    QDRANT_CLOUD_API_KEY,
    QDRANT_CLOUD_URL,
    QDRANT_GRPC_PORT,
    QDRANT_HOST,
    USE_CLOUD_QDRANT,
)

logger = logging.getLogger(__name__)

_RETRYABLE_TERMS = frozenset(["timed out", "timeout", "connection", "disconnected"])


def _with_retry(method, *, max_retries=3, base_backoff=1.0):
    """Add exponential backoff retry to a method for transient timeout/connection errors."""

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return method(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                error_str = str(e).lower()
                if not any(term in error_str for term in _RETRYABLE_TERMS):
                    raise
                backoff = base_backoff * (2**attempt)
                logger.warning(
                    f"Qdrant {method.__name__} transient error "
                    f"(attempt {attempt + 1}/{max_retries}), retrying in {backoff:.0f}s: {e}"
                )
                time.sleep(backoff)

    return wrapper


def get_qdrant_client() -> QdrantClient:
    """
    Returns a Qdrant client based on the configured settings.

    Uses cloud Qdrant if USE_CLOUD_QDRANT=true, otherwise uses local.
    query_points and scroll are patched with retry logic for transient errors.

    Returns:
        QdrantClient: Configured Qdrant client
    """
    if USE_CLOUD_QDRANT:
        if not QDRANT_CLOUD_URL or not QDRANT_CLOUD_API_KEY:
            raise ValueError(
                "USE_CLOUD_QDRANT is enabled but QDRANT_CLOUD_URL or "
                "QDRANT_CLOUD_API_KEY environment variables are not set"
            )

        client = QdrantClient(
            url=QDRANT_CLOUD_URL,
            api_key=QDRANT_CLOUD_API_KEY,
            timeout=360,
        )
        logger.info(f"Connecting to Qdrant Cloud: {QDRANT_CLOUD_URL}")
    else:
        client = QdrantClient(
            url=QDRANT_HOST,
            port=QDRANT_GRPC_PORT,
            api_key=QDRANT_API_KEY,
            timeout=360,  # Increased for large document batches (caselaw can be 260K+ chars)
        )
        logger.info(f"Connecting to local Qdrant: {QDRANT_HOST}")

    try:
        # Test connection
        collections = client.get_collections()
        mode = "Cloud" if USE_CLOUD_QDRANT else "Local"
        logger.info(
            f"Connected to Qdrant ({mode})",
            extra={
                "collections_count": len(collections.collections),
                "mode": mode,
            },
        )
        # Patch query_points and scroll with retry for transient errors
        client.query_points = _with_retry(client.query_points)
        client.scroll = _with_retry(client.scroll)

        return client
    except Exception as e:
        mode = "Cloud" if USE_CLOUD_QDRANT else "Local"
        logger.error(f"Error connecting to Qdrant ({mode}): {e}")
        raise


def _with_async_retry(method, *, max_retries=3, base_backoff=1.0):
    """Add exponential backoff retry to an async method for transient errors."""

    @functools.wraps(method)
    async def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return await method(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                error_str = str(e).lower()
                if not any(term in error_str for term in _RETRYABLE_TERMS):
                    raise
                backoff = base_backoff * (2**attempt)
                logger.warning(
                    f"Qdrant async {method.__name__} transient error "
                    f"(attempt {attempt + 1}/{max_retries}), retrying in {backoff:.0f}s: {e}"
                )
                await asyncio.sleep(backoff)

    return wrapper


def get_async_qdrant_client() -> AsyncQdrantClient:
    """Returns an async Qdrant client for use in FastAPI endpoints."""
    if USE_CLOUD_QDRANT:
        if not QDRANT_CLOUD_URL or not QDRANT_CLOUD_API_KEY:
            raise ValueError(
                "USE_CLOUD_QDRANT is enabled but QDRANT_CLOUD_URL or "
                "QDRANT_CLOUD_API_KEY environment variables are not set"
            )
        client = AsyncQdrantClient(
            url=QDRANT_CLOUD_URL,
            api_key=QDRANT_CLOUD_API_KEY,
            timeout=360,
        )
        logger.info(f"Created async Qdrant Cloud client: {QDRANT_CLOUD_URL}")
    else:
        client = AsyncQdrantClient(
            url=QDRANT_HOST,
            port=QDRANT_GRPC_PORT,
            api_key=QDRANT_API_KEY,
            timeout=360,
        )
        logger.info(f"Created async local Qdrant client: {QDRANT_HOST}")

    # Patch with async retry for transient errors
    client.query_points = _with_async_retry(client.query_points)
    client.scroll = _with_async_retry(client.scroll)
    client.count = _with_async_retry(client.count)
    client.get_collection = _with_async_retry(client.get_collection)
    client.get_collections = _with_async_retry(client.get_collections)

    return client


# Lazy-initialised global sync client (used by scripts, ingest, tests)
_qdrant_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = get_qdrant_client()
    return _qdrant_client


class _LazyClient:
    """Proxy that defers Qdrant connection until first attribute access."""

    def __getattr__(self, name: str):
        return getattr(_get_client(), name)


qdrant_client: QdrantClient = _LazyClient()  # type: ignore[assignment]


# Lazy-initialised global async client (used by FastAPI endpoints)
_async_qdrant_client: AsyncQdrantClient | None = None


def _get_async_client() -> AsyncQdrantClient:
    global _async_qdrant_client
    if _async_qdrant_client is None:
        _async_qdrant_client = get_async_qdrant_client()
    return _async_qdrant_client


class _LazyAsyncClient:
    """Proxy that defers async Qdrant connection until first attribute access."""

    def __getattr__(self, name: str):
        return getattr(_get_async_client(), name)


async_qdrant_client: AsyncQdrantClient = _LazyAsyncClient()  # type: ignore[assignment]
