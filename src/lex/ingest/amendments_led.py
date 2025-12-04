"""Amendment-led ingestion logic.

Queries the amendments collection to identify which legislation
has been amended recently, then rescapes only those items.

This module provides the core functions for the amendments-led ingest mode,
which uses amendments as a "change manifest" to determine which legislation
needs refreshing instead of blindly rescraping by year.
"""

import logging

from qdrant_client.models import FieldCondition, Filter, MatchAny

from lex.core.qdrant_client import qdrant_client
from lex.ingest.state import get_existing_ids
from lex.settings import AMENDMENT_COLLECTION, LEGISLATION_COLLECTION

logger = logging.getLogger(__name__)


def get_changed_legislation_ids(years: list[int]) -> set[str]:
    """Get unique legislation IDs that were amended in the given years.

    Queries amendments by `affecting_year` (when the amendment was made)
    and extracts unique `changed_legislation` values.

    Args:
        years: List of years to query (e.g., [2024, 2025])

    Returns:
        Set of legislation IDs (e.g., {"ukpga/2020/1", "uksi/2023/456"})
    """
    changed_ids: set[str] = set()
    offset = None
    total_amendments = 0

    logger.info(f"Querying amendments for affecting_year in {years}")

    while True:
        points, offset = qdrant_client.scroll(
            collection_name=AMENDMENT_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="affecting_year",
                        match=MatchAny(any=years),
                    )
                ]
            ),
            limit=1000,
            offset=offset,
            with_payload=["changed_legislation"],
            with_vectors=False,
        )

        if not points:
            break

        for point in points:
            leg_id = point.payload.get("changed_legislation")
            if leg_id:
                changed_ids.add(leg_id)

        total_amendments += len(points)

        if offset is None:
            break

    logger.info(
        f"Found {len(changed_ids)} unique legislation IDs "
        f"from {total_amendments} amendments in years {years}"
    )
    return changed_ids


def get_missing_legislation_ids(legislation_ids: set[str]) -> set[str]:
    """Return legislation IDs that don't exist in Qdrant.

    Uses the efficient batch lookup pattern from state.py.

    Args:
        legislation_ids: Set of legislation IDs to check

    Returns:
        Set of legislation IDs that need to be scraped
    """
    if not legislation_ids:
        return set()

    existing = get_existing_ids(LEGISLATION_COLLECTION, list(legislation_ids))
    missing = legislation_ids - existing

    logger.info(
        f"Legislation status: {len(existing)} exist, {len(missing)} missing/stale"
    )
    return missing


def parse_legislation_id(leg_id: str) -> tuple[str, int, int] | None:
    """Parse legislation ID into components.

    Args:
        leg_id: ID like "ukpga/2020/1" or "uksi/2023/456"

    Returns:
        Tuple of (type, year, number) or None if invalid
    """
    try:
        parts = leg_id.split("/")
        if len(parts) >= 3:
            return parts[0], int(parts[1]), int(parts[2])
    except (ValueError, IndexError):
        pass
    return None
