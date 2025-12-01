"""Qdrant collection schemas for caselaw."""

from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from lex.settings import (
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    CASELAW_SUMMARY_COLLECTION,
    EMBEDDING_DIMENSIONS,
)


def get_caselaw_schema():
    """
    Schema for caselaw (full judgments) collection.

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance)
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All Caselaw fields from Pydantic model
    - Indexed fields: id, court, division, year (for fast filtering)
    """
    return {
        "collection_name": CASELAW_COLLECTION,
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
            "court": PayloadSchemaType.KEYWORD,  # Filter by court
            "division": PayloadSchemaType.KEYWORD,  # Filter by division
            "year": PayloadSchemaType.INTEGER,  # Range queries (year_from/year_to)
            "legislation_references": PayloadSchemaType.KEYWORD,  # Filter by legislation references
            "caselaw_references": PayloadSchemaType.KEYWORD,  # Filter by caselaw references
        },
        "quantization_config": ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )
        ),
    }


def get_caselaw_section_schema():
    """
    Schema for caselaw_section collection.

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance)
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All CaselawSection fields from Pydantic model
    - Indexed fields: id, caselaw_id, court, division, year (for fast filtering)
    """
    return {
        "collection_name": CASELAW_SECTION_COLLECTION,
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
            "id": PayloadSchemaType.KEYWORD,  # Exact match for section lookups
            "caselaw_id": PayloadSchemaType.KEYWORD,  # Filter by parent caselaw
            "court": PayloadSchemaType.KEYWORD,  # Filter by court
            "division": PayloadSchemaType.KEYWORD,  # Filter by division
            "year": PayloadSchemaType.INTEGER,  # Range queries (year_from/year_to)
        },
        "quantization_config": ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )
        ),
    }


def get_caselaw_summary_schema():
    """
    Schema for caselaw_summary collection (AI-generated summaries).

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance)
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All CaselawSummary fields from Pydantic model
    - Indexed fields: id, caselaw_id, court, division, year (for fast filtering)
    """
    return {
        "collection_name": CASELAW_SUMMARY_COLLECTION,
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
            "caselaw_id": PayloadSchemaType.KEYWORD,  # Filter by parent caselaw
            "court": PayloadSchemaType.KEYWORD,  # Filter by court
            "division": PayloadSchemaType.KEYWORD,  # Filter by division
            "year": PayloadSchemaType.INTEGER,  # Range queries (year_from/year_to)
        },
        "quantization_config": ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )
        ),
    }
