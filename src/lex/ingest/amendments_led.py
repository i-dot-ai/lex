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
from lex.ingest.state import get_existing_ids_with_metadata
from lex.settings import AMENDMENT_COLLECTION, LEGISLATION_COLLECTION

logger = logging.getLogger(__name__)

# Retry config for Qdrant queries
MAX_SCROLL_RETRIES = 3
SCROLL_RETRY_DELAY = 5.0


def get_changed_legislation_ids(years: list[int]) -> dict[str, int]:
    """Get unique legislation IDs that were amended in the given years.

    Queries amendments by `affecting_year` (when the amendment was made)
    and extracts unique `changed_legislation` values with their latest
    amendment year (for staleness comparison).

    Args:
        years: List of years to query (e.g., [2024, 2025])

    Returns:
        Dict mapping legislation ID to max affecting year,
        e.g., {"ukpga/2020/1": 2025, "uksi/2023/456": 2024}
    """
    changed_ids: dict[str, int] = {}
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
                    with_payload=["changed_legislation", "affecting_year"],
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
            affecting_year = point.payload.get("affecting_year")
            if leg_id and affecting_year:
                changed_ids[leg_id] = max(changed_ids.get(leg_id, 0), affecting_year)

        total_amendments += len(points)

        if offset is None:
            break

    logger.info(
        f"Found {len(changed_ids)} unique legislation IDs "
        f"from {total_amendments} amendments in years {years}"
    )
    return changed_ids


def get_stale_or_missing_legislation_ids(
    changed_legislation: dict[str, int],
) -> set[str]:
    """Return legislation IDs that are missing or stale in Qdrant.

    Checks both existence and staleness. An item is stale if its
    modified_date is older than the year it was last amended.

    Note: Amendment IDs use the short form (e.g., "ukpga/2020/1") but
    legislation in Qdrant uses full URIs (e.g., "http://www.legislation.gov.uk/id/ukpga/2020/1").

    Args:
        changed_legislation: Dict mapping short-form legislation ID
            to max affecting year (from amendments)

    Returns:
        Set of short-form legislation IDs that need to be scraped
    """
    from datetime import date

    if not changed_legislation:
        return set()

    # Convert short IDs to full URIs to match what's stored in Qdrant
    base_uri = "http://www.legislation.gov.uk/id/"
    short_to_full = {lid: f"{base_uri}{lid}" for lid in changed_legislation}
    full_ids = list(short_to_full.values())

    # Retrieve existence + modified_date for staleness comparison
    existing_metadata = get_existing_ids_with_metadata(LEGISLATION_COLLECTION, full_ids)

    # Build reverse mapping: full URI -> short ID
    full_to_short = {v: k for k, v in short_to_full.items()}

    missing = set()
    stale = set()
    up_to_date = set()

    for short_id, full_id in short_to_full.items():
        if full_id not in existing_metadata:
            missing.add(short_id)
            continue

        metadata = existing_metadata[full_id]
        modified_date_str = metadata.get("modified_date")
        max_amendment_year = changed_legislation[short_id]

        # Parse modified_date (stored as ISO string in Qdrant payload)
        if modified_date_str is None:
            stale.add(short_id)
            continue

        try:
            if isinstance(modified_date_str, str):
                modified_year = date.fromisoformat(modified_date_str).year
            else:
                modified_year = modified_date_str.year
        except (ValueError, AttributeError):
            stale.add(short_id)
            continue

        if modified_year < max_amendment_year:
            stale.add(short_id)
        else:
            up_to_date.add(short_id)

    needs_rescrape = missing | stale

    logger.info(
        f"Legislation status: {len(up_to_date)} up-to-date, "
        f"{len(stale)} stale, {len(missing)} missing"
    )
    return needs_rescrape


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
