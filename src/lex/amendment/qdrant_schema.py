"""Qdrant collection schemas for amendments."""

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

from lex.settings import AMENDMENT_COLLECTION, EMBEDDING_DIMENSIONS


def get_amendment_schema():
    """
    Schema for amendment collection.

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance)
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All Amendment fields from Pydantic model
    - Indexed fields: changed_url, affecting_url, changed_provision_url, affecting_provision_url
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
        "payload_schema": {
            "changed_url": PayloadSchemaType.KEYWORD,  # Filter amendments to legislation
            "affecting_url": PayloadSchemaType.KEYWORD,  # Filter amendments by legislation
            "changed_provision_url": PayloadSchemaType.KEYWORD,  # Filter amendments to provision
            "affecting_provision_url": PayloadSchemaType.KEYWORD,  # Filter amendments by provision
            "affecting_year": PayloadSchemaType.INTEGER,  # Filter by year amendment was made (for amendments-led ingest)
            "changed_legislation": PayloadSchemaType.KEYWORD,  # Filter by affected legislation ID
        },
        "quantization_config": ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )
        ),
    }
