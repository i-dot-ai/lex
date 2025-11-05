"""Qdrant collection schemas for legislation."""

from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from lex.settings import (
    EMBEDDING_DIMENSIONS,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)


def get_legislation_schema():
    """
    Schema for legislation (Acts) collection.

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance) from title + type + description
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All Legislation fields from Pydantic model
    - Indexed fields: id, type, year, number (for fast exact lookups)

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
        "payload_schema": {
            "id": PayloadSchemaType.KEYWORD,  # Exact match lookups
            "type": PayloadSchemaType.KEYWORD,  # Exact match lookups
            "year": PayloadSchemaType.INTEGER,  # Range queries
            "number": PayloadSchemaType.INTEGER,  # Exact match lookups
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
    - Indexed fields: id, legislation_id, legislation_type, legislation_year (for fast filtering)
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
        "payload_schema": {
            "id": PayloadSchemaType.KEYWORD,  # Exact match for provision lookups
            "legislation_id": PayloadSchemaType.KEYWORD,  # Filter by parent legislation
            "legislation_type": PayloadSchemaType.KEYWORD,  # Filter by legislation type
            "legislation_year": PayloadSchemaType.INTEGER,  # Range queries (year_from/year_to)
            "provision_type": PayloadSchemaType.KEYWORD,  # Filter by section/schedule type
        },
    }
