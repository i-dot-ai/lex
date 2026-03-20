"""Qdrant collection schemas for caselaw."""

from qdrant_client.models import PayloadSchemaType

from lex.core.qdrant_schema import build_collection_schema
from lex.settings import (
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    CASELAW_SUMMARY_COLLECTION,
)


def get_caselaw_schema():
    """
    Schema for caselaw (full judgments) collection.

    Payload indexed fields: id, court, division, year,
    legislation_references, caselaw_references.
    """
    return build_collection_schema(
        collection_name=CASELAW_COLLECTION,
        payload_schema={
            "id": PayloadSchemaType.KEYWORD,
            "court": PayloadSchemaType.KEYWORD,
            "division": PayloadSchemaType.KEYWORD,
            "year": PayloadSchemaType.INTEGER,
            "legislation_references": PayloadSchemaType.KEYWORD,
            "caselaw_references": PayloadSchemaType.KEYWORD,
        },
    )


def get_caselaw_section_schema():
    """
    Schema for caselaw_section collection.

    Payload indexed fields: id, caselaw_id, court, division, year.
    """
    return build_collection_schema(
        collection_name=CASELAW_SECTION_COLLECTION,
        payload_schema={
            "id": PayloadSchemaType.KEYWORD,
            "caselaw_id": PayloadSchemaType.KEYWORD,
            "court": PayloadSchemaType.KEYWORD,
            "division": PayloadSchemaType.KEYWORD,
            "year": PayloadSchemaType.INTEGER,
        },
    )


def get_caselaw_summary_schema():
    """
    Schema for caselaw_summary collection (AI-generated summaries).

    Payload indexed fields: id, caselaw_id, court, division, year.
    """
    return build_collection_schema(
        collection_name=CASELAW_SUMMARY_COLLECTION,
        payload_schema={
            "id": PayloadSchemaType.KEYWORD,
            "caselaw_id": PayloadSchemaType.KEYWORD,
            "court": PayloadSchemaType.KEYWORD,
            "division": PayloadSchemaType.KEYWORD,
            "year": PayloadSchemaType.INTEGER,
        },
    )
