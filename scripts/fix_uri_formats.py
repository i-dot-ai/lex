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
    USE_CLOUD_QDRANT=true uv run python scripts/fix_uri_formats.py

    # Apply fixes
    USE_CLOUD_QDRANT=true uv run python scripts/fix_uri_formats.py --apply

    # Fix specific collection only
    USE_CLOUD_QDRANT=true uv run python scripts/fix_uri_formats.py --apply --collection amendments
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
from lex.core.uri import normalise_legislation_uri
from lex.settings import (
    AMENDMENT_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Collection -> fields containing legislation URIs that need normalisation
COLLECTION_URI_FIELDS = {
    AMENDMENT_COLLECTION: ["changed_url", "affecting_url"],
    LEGISLATION_COLLECTION: ["id", "uri"],
    LEGISLATION_SECTION_COLLECTION: ["id", "uri", "legislation_id"],
    EXPLANATORY_NOTE_COLLECTION: ["legislation_id"],
}

OPERATIONS_BATCH_SIZE = 1000
DEFAULT_SCROLL_BATCH_SIZE = 1000


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
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Processing: {collection_name}")
    logger.info(f"URI fields: {uri_fields}")
    logger.info("=" * 60)

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
        "field_counts": {field: 0 for field in uri_fields},
    }

    offset = None
    batch_num = 0
    pending_operations = []
    start_time = time.time()

    while True:
        batch_num += 1

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
                            client.batch_update_points(
                                collection_name=collection_name,
                                update_operations=pending_operations,
                                wait=False,
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
            pct = 100 * stats["records_checked"] / total_points if total_points else 0
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

    # Send remaining operations
    if pending_operations and apply:
        try:
            client.batch_update_points(
                collection_name=collection_name,
                update_operations=pending_operations,
                wait=True,
            )
            stats["records_fixed"] += len(pending_operations)
            stats["batches_sent"] += 1
            logger.info(f"  Sent final batch {stats['batches_sent']}")
        except Exception as e:
            logger.error(f"Final batch update failed: {e}")
            stats["errors"] += len(pending_operations)

    # Summary
    elapsed = time.time() - start_time
    mode = "APPLIED" if apply else "DRY RUN"
    logger.info(f"\n  [{mode}] Results for {collection_name}:")
    logger.info(f"    Time:     {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    logger.info(f"    Checked:  {stats['records_checked']:,}")
    logger.info(f"    Affected: {stats['records_affected']:,}")
    for field, count in stats["field_counts"].items():
        logger.info(f"    Field '{field}': {count:,} non-canonical values")
    if apply:
        logger.info(f"    Fixed:    {stats['records_fixed']:,}")
        logger.info(f"    Batches:  {stats['batches_sent']:,}")
        logger.info(f"    Errors:   {stats['errors']:,}")

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

    logger.info("=" * 60)
    logger.info("URI FORMAT NORMALISATION")
    logger.info("=" * 60)
    logger.info(f"Mode: {'APPLY FIXES' if args.apply else 'DRY RUN (preview only)'}")
    logger.info("Canonical format: http://www.legislation.gov.uk/id/{type}/{year}/{number}")
    logger.info("")

    if not args.apply:
        logger.info("Running in DRY RUN mode. Use --apply to fix data.\n")

    client = get_qdrant_client()

    # Determine which collections to process
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
