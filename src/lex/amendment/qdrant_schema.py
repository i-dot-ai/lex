"""Qdrant collection schemas for amendments."""

from qdrant_client.models import PayloadSchemaType

from lex.core.qdrant_schema import build_collection_schema
from lex.settings import AMENDMENT_COLLECTION


def get_amendment_schema():
    """
    Schema for amendment collection.

    Payload indexed fields: changed_url, affecting_url, changed_provision_url,
    affecting_provision_url, affecting_year, changed_legislation.
    """
    return build_collection_schema(
        collection_name=AMENDMENT_COLLECTION,
        payload_schema={
            "changed_url": PayloadSchemaType.KEYWORD,
            "affecting_url": PayloadSchemaType.KEYWORD,
            "changed_provision_url": PayloadSchemaType.KEYWORD,
            "affecting_provision_url": PayloadSchemaType.KEYWORD,
            "affecting_year": PayloadSchemaType.INTEGER,
            "changed_legislation": PayloadSchemaType.KEYWORD,
        },
    )
