"""Qdrant-based state management for ingestion.

Replaces JSONL file tracking with bulk Qdrant existence queries.
Uses retrieve() which only returns points that exist - efficient for batch checks.
"""

import logging
from typing import Any

from lex.core.document import uri_to_uuid
from lex.core.qdrant_client import qdrant_client

logger = logging.getLogger(__name__)


def get_existing_ids(collection: str, doc_ids: list[str]) -> set[str]:
    """Check which documents already exist in Qdrant (batch query).

    Uses qdrant_client.retrieve() which only returns points that exist,
    making it efficient for batch existence checks.

    Args:
        collection: Name of the Qdrant collection
        doc_ids: List of document IDs (URIs) to check

    Returns:
        Set of document IDs that already exist in the collection
    """
    if not doc_ids:
        return set()

    # Convert URIs to deterministic UUIDs
    uuids = [uri_to_uuid(doc_id) for doc_id in doc_ids]

    try:
        # retrieve() only returns points that exist - efficient batch check
        results = qdrant_client.retrieve(
            collection_name=collection,
            ids=uuids,
            with_payload=["id"],
            with_vectors=False,
        )

        # Extract the original IDs from payloads
        existing = {r.payload["id"] for r in results if r.payload}
        logger.debug(f"Found {len(existing)}/{len(doc_ids)} existing in {collection}")
        return existing

    except Exception as e:
        logger.warning(f"Failed to check existing IDs in {collection}: {e}")
        return set()


def get_existing_ids_with_metadata(
    collection: str, doc_ids: list[str], fields: list[str] | None = None
) -> dict[str, dict]:
    """Check which documents exist in Qdrant and return their metadata.

    Like get_existing_ids but also retrieves specified payload fields,
    useful for staleness detection.

    Args:
        collection: Name of the Qdrant collection
        doc_ids: List of document IDs (URIs) to check
        fields: Payload fields to retrieve (default: ["id", "modified_date"])

    Returns:
        Dict mapping document ID to its payload metadata
    """
    if not doc_ids:
        return {}

    if fields is None:
        fields = ["id", "modified_date"]

    uuids = [uri_to_uuid(doc_id) for doc_id in doc_ids]

    try:
        results = qdrant_client.retrieve(
            collection_name=collection,
            ids=uuids,
            with_payload=fields,
            with_vectors=False,
        )

        existing = {}
        for r in results:
            if r.payload and "id" in r.payload:
                existing[r.payload["id"]] = r.payload

        logger.debug(f"Found {len(existing)}/{len(doc_ids)} existing in {collection}")
        return existing

    except Exception as e:
        logger.warning(f"Failed to check existing IDs with metadata in {collection}: {e}")
        return {}


def filter_new_items(
    collection: str,
    items: list[Any],
    id_field: str = "id",
) -> list[Any]:
    """Filter list to only items not already in Qdrant.

    Args:
        collection: Name of the Qdrant collection
        items: List of items with an ID field
        id_field: Name of the attribute containing the document ID

    Returns:
        List of items not already in the collection
    """
    if not items:
        return []

    all_ids = [getattr(item, id_field) for item in items]
    existing = get_existing_ids(collection, all_ids)

    new_items = [item for item in items if getattr(item, id_field) not in existing]

    if existing:
        logger.info(f"Skipping {len(existing)} existing, processing {len(new_items)} new items")

    return new_items


def count_documents(collection: str) -> int:
    """Get the count of documents in a collection.

    Args:
        collection: Name of the Qdrant collection

    Returns:
        Number of documents in the collection
    """
    try:
        info = qdrant_client.get_collection(collection)
        return info.points_count or 0
    except Exception:
        return 0
