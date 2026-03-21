#!/usr/bin/env python
"""
Fix computed metadata fields on legislation_section documents in Qdrant.

ROOT CAUSE:
The deleted PDF batch uploader (qdrant_uploader.py) used model_dump(mode="json")
to serialise LegislationSection models. The @computed_field properties
(legislation_year, legislation_type, legislation_number) were computed at upload
time from malformed id/legislation_id values, storing wrong data:
  - SI numbers stored as years (e.g. SI 1845 → legislation_year=1845)
  - Regnal year URIs → legislation_year=None
  - Some sections had id == legislation_id (no /section/N suffix)

SCALE:
  - ~347K sections with legislation_year < 1200 (impossible)
  - ~42K sections with legislation_year > 2026
  - ~628K sections with null legislation_year
  - Total: ~1M sections with bad metadata (48% of 2.1M)

FIX:
Recompute all three fields from the stored legislation_id (which is correct)
using _parse_year_from_legislation_id() and update payloads via set_payload().
No re-embedding needed — vectors are untouched.

Usage:
    # Dry run (default) — report counts of incorrect metadata
    USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_section_metadata.py

    # Apply fixes
    USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_section_metadata.py --apply
"""

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))  # scripts/ directory

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env", override=True)

from _console import console, print_header, print_summary, setup_logging  # noqa: E402
from qdrant_client import models  # noqa: E402
from rich.progress import Progress  # noqa: E402

from lex.core.qdrant_client import get_qdrant_client  # noqa: E402
from lex.legislation.models import (  # noqa: E402
    LegislationType,
    _parse_year_from_legislation_id,
)
from lex.settings import LEGISLATION_SECTION_COLLECTION  # noqa: E402

logger = logging.getLogger(__name__)

OPERATIONS_BATCH_SIZE = 200
DEFAULT_SCROLL_BATCH_SIZE = 500
MAX_RETRIES = 5
BASE_BACKOFF = 2.0

# Payload fields to read from each point
READ_FIELDS = [
    "legislation_id",
    "legislation_year",
    "legislation_type",
    "legislation_number",
]


def _is_retryable(error: Exception) -> bool:
    """Check if an error is a retryable timeout/connection issue."""
    error_str = str(error).lower()
    return any(term in error_str for term in ["timed out", "timeout", "connection"])


def _retry_with_backoff(operation_name: str, operation, max_retries=MAX_RETRIES):
    """Execute an operation with exponential backoff retry for timeout errors."""
    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            if attempt == max_retries - 1 or not _is_retryable(e):
                raise
            backoff = BASE_BACKOFF * (2**attempt)
            logger.warning(
                f"{operation_name} timeout (attempt {attempt + 1}/{max_retries}), "
                f"retrying in {backoff:.0f}s..."
            )
            time.sleep(backoff)


def _extract_type_from_uri(legislation_id: str) -> str | None:
    """Extract legislation type string from a legislation_id URI.

    Example: http://www.legislation.gov.uk/id/ukpga/2018/12 → 'ukpga'
    """
    if not legislation_id:
        return None
    parts = legislation_id.split("/")
    if len(parts) < 5:
        return None
    return parts[4]


def _extract_number_from_uri(legislation_id: str) -> int | None:
    """Extract legislation number from a legislation_id URI.

    Standard: http://www.legislation.gov.uk/id/ukpga/2018/12 → 12
    Regnal:   http://www.legislation.gov.uk/id/ukla/Vict/44-45/12 → 12
    """
    if not legislation_id:
        return None
    parts = legislation_id.split("/")
    if len(parts) < 6:
        return None
    # Try standard position (index 6)
    try:
        return int(parts[6])
    except (IndexError, ValueError):
        pass
    # Fall back to last numeric component
    for part in reversed(parts):
        try:
            return int(part)
        except ValueError:
            continue
    return None


def _validate_type(type_str: str | None) -> str | None:
    """Validate that the type string is a known LegislationType value."""
    if type_str is None:
        return None
    try:
        LegislationType(type_str)
        return type_str
    except ValueError:
        return None


def _compute_corrections(payload: dict) -> dict | None:
    """Compute corrected metadata fields from legislation_id.

    Returns a dict of fields to update, or None if no changes needed.
    """
    legislation_id = payload.get("legislation_id")
    if not legislation_id:
        return None

    new_year = _parse_year_from_legislation_id(legislation_id)
    new_type = _validate_type(_extract_type_from_uri(legislation_id))
    new_number = _extract_number_from_uri(legislation_id)

    stored_year = payload.get("legislation_year")
    stored_type = payload.get("legislation_type")
    stored_number = payload.get("legislation_number")

    updates = {}
    if new_year != stored_year:
        updates["legislation_year"] = new_year
    if new_type != stored_type:
        updates["legislation_type"] = new_type
    if new_number != stored_number:
        updates["legislation_number"] = new_number

    return updates if updates else None


def fix_section_metadata(
    client,
    apply: bool = False,
    scroll_batch_size: int = DEFAULT_SCROLL_BATCH_SIZE,
) -> dict:
    """Fix computed metadata fields on all legislation_section documents."""
    collection = LEGISLATION_SECTION_COLLECTION
    console.rule(f"[bold]{collection}[/bold]")

    info = client.get_collection(collection)
    total_points = info.points_count
    console.print(f"Total documents: {total_points:,}\n")

    stats = {
        "total_records": total_points,
        "records_checked": 0,
        "records_affected": 0,
        "records_fixed": 0,
        "batches_sent": 0,
        "errors": 0,
        "year_changed": 0,
        "type_changed": 0,
        "number_changed": 0,
        "no_legislation_id": 0,
    }

    offset = None
    pending_operations = []
    start_time = time.time()

    with Progress(console=console) as progress:
        task = progress.add_task(f"Scanning {collection}", total=total_points)

        while True:
            results, next_offset = _retry_with_backoff(
                "Scroll",
                lambda: client.scroll(
                    collection_name=collection,
                    limit=scroll_batch_size,
                    offset=offset,
                    with_payload=READ_FIELDS,
                    with_vectors=False,
                ),
            )

            if not results:
                break

            for point in results:
                stats["records_checked"] += 1

                if not point.payload.get("legislation_id"):
                    stats["no_legislation_id"] += 1
                    continue

                corrections = _compute_corrections(point.payload)
                if corrections is None:
                    continue

                stats["records_affected"] += 1
                if "legislation_year" in corrections:
                    stats["year_changed"] += 1
                if "legislation_type" in corrections:
                    stats["type_changed"] += 1
                if "legislation_number" in corrections:
                    stats["number_changed"] += 1

                if apply:
                    operation = models.SetPayloadOperation(
                        set_payload=models.SetPayload(
                            payload=corrections,
                            points=[point.id],
                        )
                    )
                    pending_operations.append(operation)

                    if len(pending_operations) >= OPERATIONS_BATCH_SIZE:
                        try:
                            ops = pending_operations
                            _retry_with_backoff(
                                "Batch update",
                                lambda: client.batch_update_points(
                                    collection_name=collection,
                                    update_operations=ops,
                                    wait=False,
                                ),
                            )
                            stats["records_fixed"] += len(pending_operations)
                            stats["batches_sent"] += 1
                            logger.info(
                                f"Sent batch {stats['batches_sent']}: "
                                f"{stats['records_fixed']:,} fixed so far"
                            )
                        except Exception as e:
                            logger.error(f"Batch update failed: {e}")
                            stats["errors"] += len(pending_operations)
                        pending_operations = []

            progress.update(task, completed=stats["records_checked"])

            offset = next_offset
            if offset is None:
                break

    # Flush remaining operations
    if pending_operations and apply:
        try:
            ops = pending_operations
            _retry_with_backoff(
                "Final batch update",
                lambda: client.batch_update_points(
                    collection_name=collection,
                    update_operations=ops,
                    wait=True,
                ),
            )
            stats["records_fixed"] += len(pending_operations)
            stats["batches_sent"] += 1
            logger.info(f"Sent final batch {stats['batches_sent']}")
        except Exception as e:
            logger.error(f"Final batch update failed: {e}")
            stats["errors"] += len(pending_operations)

    elapsed = time.time() - start_time
    mode = "APPLIED" if apply else "DRY RUN"
    summary_stats = {
        "Mode": mode,
        "Time": f"{elapsed:.1f}s ({elapsed / 60:.1f} min)",
        "Checked": f"{stats['records_checked']:,}",
        "Affected": f"{stats['records_affected']:,}",
        "Year changed": f"{stats['year_changed']:,}",
        "Type changed": f"{stats['type_changed']:,}",
        "Number changed": f"{stats['number_changed']:,}",
        "No legislation_id": f"{stats['no_legislation_id']:,}",
    }
    if apply:
        summary_stats["Fixed"] = f"{stats['records_fixed']:,}"
        summary_stats["Batches"] = f"{stats['batches_sent']:,}"
        summary_stats["Errors"] = f"{stats['errors']:,}"

    print_summary(collection, summary_stats, success=stats["errors"] == 0)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Fix computed metadata fields on legislation_section documents"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply fixes (default is dry run)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_SCROLL_BATCH_SIZE,
        help=f"Batch size for scrolling (default: {DEFAULT_SCROLL_BATCH_SIZE})",
    )
    args = parser.parse_args()

    setup_logging()

    print_header(
        "Section Metadata Fix",
        mode="APPLY" if args.apply else "DRY RUN",
        details={
            "Fields": "legislation_year, legislation_type, legislation_number",
            "Source": "Recomputed from legislation_id",
            "Collection": LEGISLATION_SECTION_COLLECTION,
        },
    )

    client = get_qdrant_client()

    stats = fix_section_metadata(
        client,
        apply=args.apply,
        scroll_batch_size=args.batch_size,
    )

    if not args.apply and stats["records_affected"] > 0:
        console.print(
            f"\n[yellow]Run with --apply to fix {stats['records_affected']:,} records[/yellow]"
        )


if __name__ == "__main__":
    main()
