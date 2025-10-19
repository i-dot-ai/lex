import logging

from qdrant_client import QdrantClient

from lex.settings import QDRANT_API_KEY, QDRANT_GRPC_PORT, QDRANT_HOST

logger = logging.getLogger(__name__)


def get_qdrant_client() -> QdrantClient:
    """
    Returns a Qdrant client based on the configured settings.

    Returns:
        QdrantClient: Configured Qdrant client
    """
    client = QdrantClient(
        url=QDRANT_HOST,
        port=QDRANT_GRPC_PORT,
        api_key=QDRANT_API_KEY,
        timeout=360,  # Increased for large document batches (caselaw can be 260K+ chars)
    )

    try:
        # Test connection
        collections = client.get_collections()
        logger.info(
            f"Connected to Qdrant",
            extra={
                "collections_count": len(collections.collections),
            },
        )
        return client
    except Exception as e:
        logger.error(f"Error connecting to Qdrant: {e}")
        raise


# Global client instance
qdrant_client = get_qdrant_client()
