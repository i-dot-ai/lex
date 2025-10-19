"""Qdrant collection schemas for explanatory notes."""

from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from lex.settings import EMBEDDING_DIMENSIONS, EXPLANATORY_NOTE_COLLECTION


def get_explanatory_note_schema():
    """
    Schema for explanatory_note collection.

    Vectors:
    - dense: 1024D OpenAI embeddings (COSINE distance)
    - sparse: BM25 term weights (DOT product for BM25 scoring)

    Payload:
    - All ExplanatoryNote fields from Pydantic model
    - Indexed fields: id, legislation_id, note_type, section_type, section_number
    """
    return {
        "collection_name": EXPLANATORY_NOTE_COLLECTION,
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
            "legislation_id": PayloadSchemaType.KEYWORD,  # Filter by parent legislation
            "note_type": PayloadSchemaType.KEYWORD,  # Filter by note type (enum)
            "section_type": PayloadSchemaType.KEYWORD,  # Filter by section type (enum)
            "section_number": PayloadSchemaType.INTEGER,  # Exact match on section number
        },
    }
