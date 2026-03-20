#!/usr/bin/env python
"""
Fix URI format inconsistencies across Qdrant collections.

ROOT CAUSE:
Three ingest pipelines produce different URI formats:
1. Amendment parser uses https:// (should be http://)
2. PDF/OCR pipeline uses dc:identifier (missing /id/ segment, has /enacted suffix)
3. XML pipeline correctly uses IdURI (http://www.legislation.gov.uk/id/...)

This script normalises all URI fields to the canonical format:
    http://www.legislation.gov.uk/id/{type}/{year}/{number}

AFFECTED COLLECTIONS:
- amendments: changed_url, affecting_url use https:// scheme
- legislation: id, uri fields for PDF-sourced records (~94K)
- legislation_section: id, uri, legislation_id for PDF-sourced records (~1M)
- explanatory_note: legislation_id may have https:// or missing /id/

IMPORTANT: Payload updates do NOT affect vector indexes (HNSW or sparse).

Usage:
    # Dry run (default) - report counts of non-canonical URIs
    USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_uri_formats.py

    # Apply fixes
    USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_uri_formats.py --apply

    # Fix specific collection only
    USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_uri_formats.py --apply --collection amendments
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

from _console import console, print_header, print_summary, setup_logging
from qdrant_client import models
from rich.progress import Progress

from lex.core.qdrant_client import get_qdrant_client
from lex.core.uri import normalise_legislation_uri
from lex.settings import (
    AMENDMENT_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

logger = logging.getLogger(__name__)

# Collection -> fields containing legislation URIs that need normalisation
COLLECTION_URI_FIELDS = {
    AMENDMENT_COLLECTION: ["changed_url", "affecting_url"],
    LEGISLATION_COLLECTION: ["id", "uri"],
    LEGISLATION_SECTION_COLLECTION: ["id", "uri", "legislation_id"],
    EXPLANATORY_NOTE_COLLECTION: ["legislation_id"],
}

OPERATIONS_BATCH_SIZE = 200
DEFAULT_SCROLL_BATCH_SIZE = 500
MAX_RETRIES = 5
BASE_BACKOFF = 2.0


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


def needs_normalisation(value: str | None) -> bool:
    """Check if a URI value needs normalisation."""
    if not value or not isinstance(value, str):
        return False
    normalised = normalise_legislation_uri(value)
    return normalised != value


def fix_collection(
    client,
    collection_name: str,
    uri_fields: list[str],
    apply: bool = False,
    scroll_batch_size: int = DEFAULT_SCROLL_BATCH_SIZE,
) -> dict:
    """Fix URI fields in a collection.

    Returns stats about the operation.
    """
    console.rule(f"[bold]{collection_name}[/bold]")
    console.print(f"URI fields: {uri_fields}")

    info = client.get_collection(collection_name)
    total_points = info.points_count
    console.print(f"Total documents: {total_points:,}\n")

    stats = {
        "collection": collection_name,
        "total_records": total_points,
        "records_checked": 0,
        "records_affected": 0,
        "records_fixed": 0,
        "batches_sent": 0,
        "errors": 0,
        "field_counts": {field: 0 for field in uri_fields},
    }

    offset = None
    pending_operations = []
    start_time = time.time()

    with Progress(console=console) as progress:
        task = progress.add_task(f"Scanning {collection_name}", total=total_points)

        while True:
            results, next_offset = _retry_with_backoff(
                "Scroll",
                lambda: client.scroll(
                    collection_name=collection_name,
                    limit=scroll_batch_size,
                    offset=offset,
                    with_payload=uri_fields,
                    with_vectors=False,
                ),
            )

            if not results:
                break

            for point in results:
                stats["records_checked"] += 1
                payload_updates = {}

                for field in uri_fields:
                    value = point.payload.get(field)
                    if needs_normalisation(value):
                        payload_updates[field] = normalise_legislation_uri(value)
                        stats["field_counts"][field] += 1

                if payload_updates:
                    stats["records_affected"] += 1

                    if apply:
                        operation = models.SetPayloadOperation(
                            set_payload=models.SetPayload(
                                payload=payload_updates,
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
                                        collection_name=collection_name,
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

    # Send remaining operations
    if pending_operations and apply:
        try:
            ops = pending_operations
            _retry_with_backoff(
                "Final batch update",
                lambda: client.batch_update_points(
                    collection_name=collection_name,
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
    }
    for field, count in stats["field_counts"].items():
        summary_stats[f"Field '{field}'"] = f"{count:,} non-canonical"
    if apply:
        summary_stats["Fixed"] = f"{stats['records_fixed']:,}"
        summary_stats["Batches"] = f"{stats['batches_sent']:,}"
        summary_stats["Errors"] = f"{stats['errors']:,}"

    print_summary(collection_name, summary_stats, success=stats["errors"] == 0)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Fix URI format inconsistencies across Qdrant collections"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply fixes (default is dry run)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        choices=list(COLLECTION_URI_FIELDS.keys()),
        help="Fix only a specific collection",
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
        "URI Format Normalisation",
        mode="APPLY" if args.apply else "DRY RUN",
        details={
            "Canonical format": "http://www.legislation.gov.uk/id/{type}/{year}/{number}",
            "Collection": args.collection or "all",
        },
    )

    client = get_qdrant_client()

    if args.collection:
        collections = {args.collection: COLLECTION_URI_FIELDS[args.collection]}
    else:
        collections = COLLECTION_URI_FIELDS

    all_stats = []
    total_start = time.time()

    for collection_name, uri_fields in collections.items():
        try:
            stats = fix_collection(
                client,
                collection_name,
                uri_fields=uri_fields,
                apply=args.apply,
                scroll_batch_size=args.batch_size,
            )
            all_stats.append(stats)
        except Exception as e:
            logger.error(f"Failed to process {collection_name}: {e}")
            all_stats.append({"collection": collection_name, "error": str(e)})

    total_elapsed = time.time() - total_start
    total_affected = sum(s.get("records_affected", 0) for s in all_stats)
    total_fixed = sum(s.get("records_fixed", 0) for s in all_stats)
    total_errors = sum(s.get("errors", 0) for s in all_stats)

    summary = {
        "Total time": f"{total_elapsed:.1f}s ({total_elapsed / 60:.1f} min)",
        "Total affected": f"{total_affected:,}",
    }
    if args.apply:
        summary["Total fixed"] = f"{total_fixed:,}"
        summary["Total errors"] = f"{total_errors:,}"

    for stats in all_stats:
        if "error" in stats:
            summary[stats["collection"]] = f"ERROR - {stats['error']}"
        else:
            status = "FIXED" if args.apply and stats["records_fixed"] > 0 else "FOUND"
            summary[stats["collection"]] = f"{stats['records_affected']:,} affected [{status}]"

    print_summary("Overall Summary", summary, success=total_errors == 0)


if __name__ == "__main__":
    main()
