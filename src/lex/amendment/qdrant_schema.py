"""Qdrant collection schemas for amendments."""

from qdrant_client.models import (
    Distance,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from lex.settings import AMENDMENT_COLLECTION, EMBEDDING_DIMENSIONS


def get_amendment_schema():
    """
    Schema for amendment collection.

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance)
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All Amendment fields from Pydantic model
    """
    return {
        "collection_name": AMENDMENT_COLLECTION,
        "vectors_config": {
            "dense": VectorParams(
                size=EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            )
        },
        "sparse_vectors_config": {
            "sparse": SparseVectorParams(
                index=SparseIndexParams(
                    on_disk=False,  # Keep in memory for speed
                )
            )
        },
    }
