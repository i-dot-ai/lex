"""Qdrant collection schemas for legislation."""

from qdrant_client.models import (
    Distance,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from lex.settings import EMBEDDING_DIMENSIONS, LEGISLATION_COLLECTION, LEGISLATION_SECTION_COLLECTION


def get_legislation_schema():
    """
    Schema for legislation (Acts) collection.

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance) from title + type + description
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All Legislation fields from Pydantic model

    Purpose:
    - Enable top-level Act discovery (e.g., "Copyright Act" returns the Act itself)
    - Complement section-level search for better hybrid search quality
    - Address ranking experiment finding: need better Act-level relevance
    """
    return {
        "collection_name": LEGISLATION_COLLECTION,
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


def get_legislation_section_schema():
    """
    Schema for legislation_section collection.

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance)
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All LegislationSection fields from Pydantic model
    """
    return {
        "collection_name": LEGISLATION_SECTION_COLLECTION,
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
