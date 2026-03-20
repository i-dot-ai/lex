"""Qdrant collection schemas for legislation."""

from qdrant_client.models import PayloadSchemaType

from lex.core.qdrant_schema import build_collection_schema
from lex.settings import LEGISLATION_COLLECTION, LEGISLATION_SECTION_COLLECTION


def get_legislation_schema():
    """
    Schema for legislation (Acts) collection.

    Payload indexed fields: id, type, year, number, provenance_source.
    Enables top-level Act discovery and hybrid search quality.
    """
    return build_collection_schema(
        collection_name=LEGISLATION_COLLECTION,
        payload_schema={
            "id": PayloadSchemaType.KEYWORD,
            "type": PayloadSchemaType.KEYWORD,
            "year": PayloadSchemaType.INTEGER,
            "number": PayloadSchemaType.INTEGER,
            "provenance_source": PayloadSchemaType.KEYWORD,
        },
    )


def get_legislation_section_schema():
    """
    Schema for legislation_section collection.

    Payload indexed fields: id, legislation_id, legislation_type, legislation_year,
    provision_type, provenance_source.
    """
    return build_collection_schema(
        collection_name=LEGISLATION_SECTION_COLLECTION,
        payload_schema={
            "id": PayloadSchemaType.KEYWORD,
            "legislation_id": PayloadSchemaType.KEYWORD,
            "legislation_type": PayloadSchemaType.KEYWORD,
            "legislation_year": PayloadSchemaType.INTEGER,
            "provision_type": PayloadSchemaType.KEYWORD,
            "provenance_source": PayloadSchemaType.KEYWORD,
        },
    )
