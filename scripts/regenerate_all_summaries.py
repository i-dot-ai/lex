#!/usr/bin/env python
"""
Regenerate ALL caselaw summaries with fixed parser data.

This script:
1. Wipes the existing caselaw_summary collection
2. Fetches all caselaw from the caselaw collection (in batches)
3. Generates AI summaries using GPT-5-nano with medium reasoning
4. Uploads summaries to Qdrant with hybrid embeddings

Usage:
    # Full regeneration (wipes and rebuilds)
    USE_CLOUD_QDRANT=true uv run python scripts/regenerate_all_summaries.py

    # Test run with 100 cases
    USE_CLOUD_QDRANT=true uv run python scripts/regenerate_all_summaries.py --limit 100

    # Dry run (no writes)
    USE_CLOUD_QDRANT=true uv run python scripts/regenerate_all_summaries.py --dry-run
"""

import argparse
import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from qdrant_client.models import PointStruct

load_dotenv()

from lex.caselaw.models import Caselaw
from lex.caselaw.qdrant_schema import get_caselaw_summary_schema
from lex.core.embeddings import generate_hybrid_embeddings
from lex.core.qdrant_client import qdrant_client
from lex.core.document import uri_to_uuid
from lex.processing.caselaw_summaries.summary_generator import add_summaries_to_caselaw
from lex.settings import CASELAW_COLLECTION, CASELAW_SUMMARY_COLLECTION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_all_caselaw(batch_size: int = 1000, limit: int | None = None) -> list[Caselaw]:
    """Fetch all caselaw from Qdrant in batches."""
    logger.info(f"Fetching caselaw from {CASELAW_COLLECTION}...")

    all_cases = []
    offset = None
    batch_num = 0

    while True:
        batch_num += 1
        results, next_offset = qdrant_client.scroll(
            collection_name=CASELAW_COLLECTION,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            break

        cases = [Caselaw(**point.payload) for point in results]
        all_cases.extend(cases)

        logger.info(f"Batch {batch_num}: fetched {len(results)} cases (total: {len(all_cases)})")

        if limit and len(all_cases) >= limit:
            all_cases = all_cases[:limit]
            logger.info(f"Limit reached: {limit} cases")
            break

        offset = next_offset
        if offset is None:
            break

    logger.info(f"Fetched {len(all_cases)} total caselaw items")
    return all_cases


def reset_summary_collection(dry_run: bool = False) -> None:
    """Delete and recreate the summary collection."""
    logger.info(f"Resetting {CASELAW_SUMMARY_COLLECTION} collection...")

    if dry_run:
        logger.info("[DRY RUN] Would delete and recreate collection")
        return

    # Delete existing collection
    try:
        qdrant_client.delete_collection(CASELAW_SUMMARY_COLLECTION)
        logger.info("Deleted existing collection")
    except Exception as e:
        logger.warning(f"Collection may not exist: {e}")

    # Recreate with schema
    schema = get_caselaw_summary_schema()
    qdrant_client.create_collection(
        collection_name=schema["collection_name"],
        vectors_config=schema["vectors_config"],
        sparse_vectors_config=schema["sparse_vectors_config"],
        quantization_config=schema["quantization_config"],
    )
    logger.info("Created new collection with schema")


def upload_summaries_batch(summaries: list, batch_size: int = 100, dry_run: bool = False) -> int:
    """Generate embeddings and upload summaries to Qdrant."""
    logger.info(f"Uploading {len(summaries)} summaries...")

    if dry_run:
        logger.info(f"[DRY RUN] Would upload {len(summaries)} summaries")
        return len(summaries)

    uploaded = 0
    points = []

    for i, summary in enumerate(summaries):
        try:
            embedding_text = summary.get_embedding_text()
            dense, sparse = generate_hybrid_embeddings(embedding_text)

            # Use deterministic UUID for idempotent upserts
            point_id = str(uri_to_uuid(summary.id))

            point = PointStruct(
                id=point_id,
                vector={"dense": dense, "sparse": sparse},
                payload=summary.model_dump(mode="json"),
            )
            points.append(point)

            # Upload in batches
            if len(points) >= batch_size:
                qdrant_client.upsert(collection_name=CASELAW_SUMMARY_COLLECTION, points=points)
                uploaded += len(points)
                logger.info(f"Uploaded batch: {uploaded}/{len(summaries)}")
                points = []

        except Exception as e:
            logger.error(f"Failed to process summary {summary.id}: {e}")
            continue

    # Upload remaining
    if points:
        qdrant_client.upsert(collection_name=CASELAW_SUMMARY_COLLECTION, points=points)
        uploaded += len(points)
        logger.info(f"Uploaded final batch: {uploaded}/{len(summaries)}")

    return uploaded


def main():
    parser = argparse.ArgumentParser(description="Regenerate all caselaw summaries")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of cases to process (for testing)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=50,
        help="Number of concurrent workers for summary generation (default: 50)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for uploads (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Don't wipe collection first (incremental mode)",
    )

    args = parser.parse_args()

    start_time = time.time()
    logger.info("=" * 70)
    logger.info("CASELAW SUMMARY REGENERATION")
    logger.info("=" * 70)
    logger.info(f"Limit: {args.limit or 'ALL'}")
    logger.info(f"Workers: {args.workers}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Reset collection: {not args.no_reset}")
    logger.info("=" * 70)

    # Step 1: Reset collection (unless --no-reset)
    if not args.no_reset:
        reset_summary_collection(dry_run=args.dry_run)

    # Step 2: Fetch all caselaw
    fetch_start = time.time()
    caselaw_items = fetch_all_caselaw(limit=args.limit)
    fetch_time = time.time() - fetch_start

    if not caselaw_items:
        logger.error("No caselaw items found!")
        return

    # Stats
    text_lengths = [len(c.text) for c in caselaw_items]
    logger.info(f"\nText length stats:")
    logger.info(f"  Min: {min(text_lengths):,} chars")
    logger.info(f"  Max: {max(text_lengths):,} chars")
    logger.info(f"  Avg: {sum(text_lengths) // len(text_lengths):,} chars")

    # Step 3: Generate summaries
    logger.info("\n" + "=" * 70)
    logger.info("GENERATING SUMMARIES")
    logger.info("=" * 70)

    gen_start = time.time()

    if args.dry_run:
        logger.info(f"[DRY RUN] Would generate summaries for {len(caselaw_items)} cases")
        summaries = []
    else:
        summaries = add_summaries_to_caselaw(caselaw_items, max_workers=args.workers)

    gen_time = time.time() - gen_start

    if summaries:
        logger.info(f"\nGeneration complete:")
        logger.info(f"  Time: {gen_time:.1f}s ({gen_time/60:.1f} minutes)")
        logger.info(f"  Generated: {len(summaries)} summaries")
        logger.info(f"  Skipped: {len(caselaw_items) - len(summaries)} (too short)")
        if gen_time > 0:
            logger.info(f"  Rate: {len(summaries) / gen_time:.1f} summaries/second")

    # Step 4: Upload to Qdrant
    if summaries:
        logger.info("\n" + "=" * 70)
        logger.info("UPLOADING TO QDRANT")
        logger.info("=" * 70)

        upload_start = time.time()
        uploaded = upload_summaries_batch(summaries, batch_size=args.batch_size, dry_run=args.dry_run)
        upload_time = time.time() - upload_start

        logger.info(f"\nUpload complete in {upload_time:.1f}s")

    # Step 5: Verify
    if not args.dry_run:
        collection_info = qdrant_client.get_collection(CASELAW_SUMMARY_COLLECTION)
        logger.info(f"\nCollection status: {collection_info.status}")
        logger.info(f"Points indexed: {collection_info.points_count}")

    # Final stats
    total_time = time.time() - start_time
    logger.info("\n" + "=" * 70)
    logger.info("COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")

    if summaries and not args.dry_run:
        time_per_summary = total_time / len(summaries)
        logger.info(f"Rate: {len(summaries) / total_time:.1f} summaries/second")
        logger.info(f"Rate: {len(summaries) / total_time * 60:.0f} summaries/minute")


if __name__ == "__main__":
    main()
