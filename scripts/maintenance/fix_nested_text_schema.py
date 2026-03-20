#!/usr/bin/env python
"""
One-off script to fix nested text schema drift in Qdrant collections.

ROOT CAUSE:
Data was migrated from Elasticsearch where semantic_text type was used.
This automatically wrapped text content with inference metadata:
    {"text": "content", "inference": {"inference_id": ..., "model_settings": ..., "chunks": ...}}

AFFECTED COLLECTIONS (from analysis):
- explanatory_note: 100% affected (82,344 records)
- legislation_section: 30.2% affected (~629,000 of 2M records)
- caselaw_section: 1.9% affected (~76,800 of 4M records)
- caselaw: 0.8% affected (~490 of 61K records)

IMPORTANT: Payload updates do NOT affect vector indexes (HNSW or sparse).
This is purely a metadata update operation - fast and safe.

This script uses batch_update_points() with SetPayloadOperation for efficiency:
- Batches up to 1000 operations per API call
- Uses wait=False for async processing
- Estimated 10-30 minutes for all ~800K affected records

Usage:
    # Dry run (default)
    USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_nested_text_schema.py

    # Actually fix the data
    USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_nested_text_schema.py --apply

    # Fix specific collection only
    USE_CLOUD_QDRANT=true uv run python scripts/maintenance/fix_nested_text_schema.py --apply --collection explanatory_note
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
from lex.settings import (
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

logger = logging.getLogger(__name__)

# Collections known to have text fields that may be nested
AFFECTED_COLLECTIONS = [
    EXPLANATORY_NOTE_COLLECTION,  # 100% affected - fix first (smallest)
    LEGISLATION_SECTION_COLLECTION,  # 30% affected
    CASELAW_SECTION_COLLECTION,  # 1.9% affected
    CASELAW_COLLECTION,  # 0.8% affected
]

# Batch size for operations (Qdrant handles this well)
# Note: caselaw has very large text fields, so use smaller batches
OPERATIONS_BATCH_SIZE = 1000
CASELAW_BATCH_SIZE = 100  # Smaller for large payloads


def extract_text_from_nested(text_value) -> str | None:
    """Extract plain text from nested structure if present."""
    if text_value is None:
        return None
    if isinstance(text_value, str):
        return None  # Already correct, no fix needed
    if isinstance(text_value, dict):
        if "text" in text_value:
            return text_value["text"]
        # Fallback: serialise the dict (shouldn't happen)
        import json

        return json.dumps(text_value)
    # Unknown type - convert to string
    return str(text_value)


def fix_collection(
    client,
    collection_name: str,
    scroll_batch_size: int = 1000,
    apply: bool = False,
    operations_batch_size: int = OPERATIONS_BATCH_SIZE,
) -> dict:
    """
    Fix nested text fields in a collection using batch_update_points.

    Returns stats about the operation.
    """
    console.rule(f"[bold]{collection_name}[/bold]")

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
    }

    offset = None
    pending_operations = []
    start_time = time.time()

    with Progress(console=console) as progress:
        task = progress.add_task(f"Scanning {collection_name}", total=total_points)

        while True:
            results, next_offset = client.scroll(
                collection_name=collection_name,
                limit=scroll_batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            if not results:
                break

            for point in results:
                stats["records_checked"] += 1
                text_value = point.payload.get("text")

                fixed_text = extract_text_from_nested(text_value)
                if fixed_text is not None:
                    stats["records_affected"] += 1

                    if apply:
                        operation = models.SetPayloadOperation(
                            set_payload=models.SetPayload(
                                payload={"text": fixed_text},
                                points=[point.id],
                            )
                        )
                        pending_operations.append(operation)

                        if len(pending_operations) >= operations_batch_size:
                            try:
                                client.batch_update_points(
                                    collection_name=collection_name,
                                    update_operations=pending_operations,
                                    wait=False,  # Async for speed
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

    # Send any remaining operations
    if pending_operations and apply:
        try:
            client.batch_update_points(
                collection_name=collection_name,
                update_operations=pending_operations,
                wait=True,  # Wait for final batch
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
    if apply:
        summary_stats["Fixed"] = f"{stats['records_fixed']:,}"
        summary_stats["Batches"] = f"{stats['batches_sent']:,}"
        summary_stats["Errors"] = f"{stats['errors']:,}"

    print_summary(collection_name, summary_stats, success=stats["errors"] == 0)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Fix nested text schema drift in Qdrant collections"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply fixes (default is dry run)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        choices=AFFECTED_COLLECTIONS,
        help="Fix only a specific collection",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for scrolling (default: 1000)",
    )
    args = parser.parse_args()

    setup_logging()

    print_header(
        "Fix Nested Text Schema",
        mode="APPLY" if args.apply else "DRY RUN",
        details={
            "Strategy": "Extract plain text from nested {text, inference} structures",
            "Collection": args.collection or "all",
        },
    )

    client = get_qdrant_client()

    collections = [args.collection] if args.collection else AFFECTED_COLLECTIONS

    all_stats = []
    total_start = time.time()

    for collection_name in collections:
        try:
            ops_batch_size = (
                CASELAW_BATCH_SIZE
                if collection_name == CASELAW_COLLECTION
                else OPERATIONS_BATCH_SIZE
            )
            stats = fix_collection(
                client,
                collection_name,
                scroll_batch_size=args.batch_size,
                apply=args.apply,
                operations_batch_size=ops_batch_size,
            )
            all_stats.append(stats)
        except Exception as e:
            logger.error(f"Failed to process {collection_name}: {e}")
            all_stats.append(
                {
                    "collection": collection_name,
                    "error": str(e),
                }
            )

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
