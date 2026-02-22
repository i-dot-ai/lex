"""Amendment-led ingestion logic.

Queries the amendments collection to identify which legislation
has been amended recently, then rescapes only those items.

This module provides the core functions for the amendments-led ingest mode,
which uses amendments as a "change manifest" to determine which legislation
needs refreshing instead of blindly rescraping by year.
"""

import logging
import time

from qdrant_client.models import FieldCondition, Filter, MatchAny

from lex.core.qdrant_client import qdrant_client
from lex.ingest.state import get_existing_ids
from lex.settings import AMENDMENT_COLLECTION, LEGISLATION_COLLECTION

logger = logging.getLogger(__name__)

# Retry config for Qdrant queries
MAX_SCROLL_RETRIES = 3
SCROLL_RETRY_DELAY = 5.0


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
        # Retry loop for transient connection issues
        points = None
        for attempt in range(MAX_SCROLL_RETRIES):
            try:
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
                break  # Success
            except Exception as e:
                if attempt < MAX_SCROLL_RETRIES - 1:
                    logger.warning(
                        f"Qdrant scroll failed (attempt {attempt + 1}/{MAX_SCROLL_RETRIES}): {e}, "
                        f"retrying in {SCROLL_RETRY_DELAY}s"
                    )
                    time.sleep(SCROLL_RETRY_DELAY)
                else:
                    logger.error(f"Qdrant scroll failed after {MAX_SCROLL_RETRIES} attempts")
                    raise

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

    Note: Amendment IDs use the short form (e.g., "ukpga/2020/1") but
    legislation in Qdrant uses full URIs (e.g., "http://www.legislation.gov.uk/id/ukpga/2020/1").
    We convert to full URIs for the lookup, then map back to short IDs.

    Args:
        legislation_ids: Set of short-form legislation IDs to check

    Returns:
        Set of short-form legislation IDs that need to be scraped
    """
    if not legislation_ids:
        return set()

    # Convert short IDs to full URIs to match what's stored in Qdrant
    base_uri = "http://www.legislation.gov.uk/id/"
    short_to_full = {lid: f"{base_uri}{lid}" for lid in legislation_ids}
    full_ids = list(short_to_full.values())

    existing_full = get_existing_ids(LEGISLATION_COLLECTION, full_ids)

    # Map back to short IDs
    existing_short = set()
    for short_id, full_id in short_to_full.items():
        if full_id in existing_full:
            existing_short.add(short_id)

    missing = legislation_ids - existing_short

    logger.info(f"Legislation status: {len(existing_short)} exist, {len(missing)} missing/stale")
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
