"""Embedding cache using Qdrant for fast lookup of previously generated embeddings."""

import hashlib
import logging
import uuid
from typing import Optional, Tuple

from qdrant_client.models import Distance, PointStruct, SparseVector, VectorParams

from lex.core.qdrant_client import qdrant_client

logger = logging.getLogger(__name__)

CACHE_COLLECTION = "embedding_cache"


def _ensure_cache_collection():
    """Create embedding cache collection if it doesn't exist."""
    try:
        qdrant_client.get_collection(CACHE_COLLECTION)
        logger.debug(f"Cache collection {CACHE_COLLECTION} already exists")
    except Exception:
        logger.info(f"Creating cache collection {CACHE_COLLECTION}")
        qdrant_client.create_collection(
            collection_name=CACHE_COLLECTION,
            vectors_config={
                "dense": VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                )
            },
            # No sparse vectors needed - we store them in payload
        )


def _query_hash(query: str) -> str:
    """Generate deterministic hash for cache key."""
    return hashlib.sha256(query.encode()).hexdigest()


def get_cached_embeddings(query: str) -> Optional[Tuple[list[float], SparseVector]]:
    """Retrieve cached embeddings for a query using direct point ID lookup.

    Returns:
        Tuple of (dense_vector, sparse_vector) if cached, None otherwise
    """
    try:
        _ensure_cache_collection()

        query_hash = _query_hash(query)
        # Generate the same deterministic ID used when caching
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, query_hash))

        # Direct point retrieval by ID (O(1) instead of O(n) filtered scan)
        points = qdrant_client.retrieve(
            collection_name=CACHE_COLLECTION,
            ids=[point_id],
            with_payload=True,
            with_vectors=True,
        )

        if points:
            point = points[0]
            dense = point.vector["dense"]
            sparse = SparseVector(
                indices=point.payload["sparse_indices"],
                values=point.payload["sparse_values"],
            )
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return (dense, sparse)

        logger.debug(f"Cache miss for query: {query[:50]}...")
        return None

    except Exception as e:
        logger.warning(f"Error retrieving from cache: {e}")
        return None


def cache_embeddings(query: str, dense: list[float], sparse: SparseVector):
    """
    Store embeddings in cache.

    Args:
        query: The search query text
        dense: Dense embedding vector (1024D)
        sparse: Sparse embedding vector (BM25)
    """
    try:
        _ensure_cache_collection()

        query_hash = _query_hash(query)

        point = PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, query_hash)),
            vector={"dense": dense},
            payload={
                "query": query,
                "query_hash": query_hash,
                "sparse_indices": sparse.indices,
                "sparse_values": sparse.values,
            },
        )

        qdrant_client.upsert(
            collection_name=CACHE_COLLECTION,
            points=[point],
        )

        logger.debug(f"Cached embeddings for query: {query[:50]}...")

    except Exception as e:
        logger.warning(f"Error caching embeddings: {e}")
