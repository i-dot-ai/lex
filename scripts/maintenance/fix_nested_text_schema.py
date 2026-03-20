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
    USE_CLOUD_QDRANT=true uv run python scripts/fix_nested_text_schema.py

    # Actually fix the data
    USE_CLOUD_QDRANT=true uv run python scripts/fix_nested_text_schema.py --apply

    # Fix specific collection only
    USE_CLOUD_QDRANT=true uv run python scripts/fix_nested_text_schema.py --apply --collection explanatory_note
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from qdrant_client import models

from lex.core.qdrant_client import get_qdrant_client
from lex.settings import (
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
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
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Processing: {collection_name}")
    logger.info("=" * 60)

    # Get collection info
    info = client.get_collection(collection_name)
    total_points = info.points_count
    logger.info(f"Total documents: {total_points:,}")

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
    batch_num = 0
    pending_operations = []
    start_time = time.time()

    while True:
        batch_num += 1

        # Scroll through collection
        results, next_offset = client.scroll(
            collection_name=collection_name,
            limit=scroll_batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            break

        # Find records needing fix and create operations
        for point in results:
            stats["records_checked"] += 1
            text_value = point.payload.get("text")

            fixed_text = extract_text_from_nested(text_value)
            if fixed_text is not None:
                stats["records_affected"] += 1

                if apply:
                    # Create a SetPayloadOperation for this point
                    operation = models.SetPayloadOperation(
                        set_payload=models.SetPayload(
                            payload={"text": fixed_text},
                            points=[point.id],
                        )
                    )
                    pending_operations.append(operation)

                    # Send batch when we hit the limit
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
                                f"  Sent batch {stats['batches_sent']}: "
                                f"{stats['records_fixed']:,} fixed so far"
                            )
                        except Exception as e:
                            logger.error(f"Batch update failed: {e}")
                            stats["errors"] += len(pending_operations)
                        pending_operations = []

        # Progress logging
        if batch_num % 10 == 0:
            pct = 100 * stats["records_checked"] / total_points
            elapsed = time.time() - start_time
            rate = stats["records_checked"] / elapsed if elapsed > 0 else 0
            eta = (total_points - stats["records_checked"]) / rate if rate > 0 else 0
            logger.info(
                f"  Progress: {stats['records_checked']:,} / {total_points:,} ({pct:.1f}%) "
                f"- Found {stats['records_affected']:,} affected - ETA: {eta / 60:.1f}min"
            )

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
            logger.info(f"  Sent final batch {stats['batches_sent']}")
        except Exception as e:
            logger.error(f"Final batch update failed: {e}")
            stats["errors"] += len(pending_operations)

    # Final summary
    elapsed = time.time() - start_time
    mode = "APPLIED" if apply else "DRY RUN"
    logger.info(f"\n  [{mode}] Results for {collection_name}:")
    logger.info(f"    Time:     {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    logger.info(f"    Checked:  {stats['records_checked']:,}")
    logger.info(f"    Affected: {stats['records_affected']:,}")
    if apply:
        logger.info(f"    Fixed:    {stats['records_fixed']:,}")
        logger.info(f"    Batches:  {stats['batches_sent']:,}")
        logger.info(f"    Errors:   {stats['errors']:,}")

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

    logger.info("=" * 60)
    logger.info("NESTED TEXT SCHEMA FIX")
    logger.info("=" * 60)
    logger.info(f"Mode: {'APPLY FIXES' if args.apply else 'DRY RUN (preview only)'}")
    logger.info("")
    logger.info("Plan:")
    logger.info("  1. Scroll through each collection")
    logger.info("  2. Identify records with nested text: {text: '...', inference: {...}}")
    logger.info("  3. Extract plain text and update using batch_update_points()")
    logger.info("  4. Payload updates do NOT affect vector indexes")
    logger.info("")

    if not args.apply:
        logger.info("⚠️  Running in DRY RUN mode. Use --apply to fix data.\n")

    # Initialise client
    client = get_qdrant_client()

    # Determine which collections to process
    collections = [args.collection] if args.collection else AFFECTED_COLLECTIONS

    # Process each collection
    all_stats = []
    total_start = time.time()

    for collection_name in collections:
        try:
            # Use smaller batch size for caselaw (very large text fields)
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

    # Summary
    total_elapsed = time.time() - total_start
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    total_affected = sum(s.get("records_affected", 0) for s in all_stats)
    total_fixed = sum(s.get("records_fixed", 0) for s in all_stats)
    total_errors = sum(s.get("errors", 0) for s in all_stats)

    for stats in all_stats:
        if "error" in stats:
            logger.info(f"  {stats['collection']}: ERROR - {stats['error']}")
        else:
            status = "FIXED" if args.apply and stats["records_fixed"] > 0 else "FOUND"
            logger.info(
                f"  {stats['collection']}: {stats['records_affected']:,} affected [{status}]"
            )

    logger.info(f"\n  Total time:     {total_elapsed:.1f}s ({total_elapsed / 60:.1f} min)")
    logger.info(f"  Total affected: {total_affected:,}")
    if args.apply:
        logger.info(f"  Total fixed:    {total_fixed:,}")
        logger.info(f"  Total errors:   {total_errors:,}")


if __name__ == "__main__":
    main()
