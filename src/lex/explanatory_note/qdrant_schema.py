"""Qdrant collection schemas for explanatory notes."""

from qdrant_client.models import PayloadSchemaType

from lex.core.qdrant_schema import build_collection_schema
from lex.settings import EXPLANATORY_NOTE_COLLECTION


def get_explanatory_note_schema():
    """
    Schema for explanatory_note collection.

    Payload indexed fields: id, legislation_id, note_type, section_type, section_number.
    """
    return build_collection_schema(
        collection_name=EXPLANATORY_NOTE_COLLECTION,
        payload_schema={
            "id": PayloadSchemaType.KEYWORD,
            "legislation_id": PayloadSchemaType.KEYWORD,
            "note_type": PayloadSchemaType.KEYWORD,
            "section_type": PayloadSchemaType.KEYWORD,
            "section_number": PayloadSchemaType.INTEGER,
        },
    )
