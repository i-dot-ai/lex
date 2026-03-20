#!/usr/bin/env python
"""
Backfill AI explanations for amendments missing them, then re-embed.

Two-phase pipeline:
  Phase 1: Generate GPT-5-nano explanations and update Qdrant payloads (legislation.gov.uk bound)
  Phase 2: Re-embed all amendments that have explanations (embedding API bound)

Usage:
    # Dry run (preview counts, no changes)
    USE_CLOUD_QDRANT=true uv run python scripts/backfill_amendment_explanations.py

    # Small test
    USE_CLOUD_QDRANT=true uv run python scripts/backfill_amendment_explanations.py --apply --limit 100

    # Full Phase 1 only (generate explanations)
    USE_CLOUD_QDRANT=true uv run python scripts/backfill_amendment_explanations.py --apply --phase 1

    # Full Phase 2 only (re-embed)
    USE_CLOUD_QDRANT=true uv run python scripts/backfill_amendment_explanations.py --apply --phase 2

    # Full run (both phases)
    USE_CLOUD_QDRANT=true uv run python scripts/backfill_amendment_explanations.py --apply
"""

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import models
from qdrant_client.models import PointStruct

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from _console import console, print_header, print_summary, setup_logging

from lex.amendment.models import Amendment
from lex.core.document import uri_to_uuid
from lex.core.embeddings import generate_hybrid_embeddings_batch
from lex.core.qdrant_client import get_qdrant_client
from lex.processing.amendment_explanations.explanation_generator import (
    generate_explanation,
)
from lex.settings import AMENDMENT_COLLECTION

logger = logging.getLogger(__name__)
qdrant_client = get_qdrant_client()


def fetch_amendments_needing_explanation(
    batch_size: int = 1000, limit: int | None = None
) -> list[Amendment]:
    """Scroll all amendments from Qdrant, returning those needing explanations."""
    logger.info(f"Scanning {AMENDMENT_COLLECTION} for amendments without explanations...")

    needing_explanation = []
    skipped_has_explanation = 0
    skipped_commencement = 0
    total_scanned = 0
    offset = None

    while True:
        results, next_offset = qdrant_client.scroll(
            collection_name=AMENDMENT_COLLECTION,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            break

        for point in results:
            total_scanned += 1
            payload = point.payload

            if payload.get("ai_explanation"):
                skipped_has_explanation += 1
                continue

            type_of_effect = payload.get("type_of_effect") or ""
            if "coming into force" in type_of_effect.lower():
                skipped_commencement += 1
                continue

            needing_explanation.append(Amendment(**payload))

            if limit and len(needing_explanation) >= limit:
                break

        if total_scanned % 100_000 == 0:
            logger.info(
                f"Scanned {total_scanned:,}... "
                f"({len(needing_explanation):,} need explanations, "
                f"{skipped_has_explanation:,} already done, "
                f"{skipped_commencement:,} commencement)"
            )

        if limit and len(needing_explanation) >= limit:
            break

        offset = next_offset
        if offset is None:
            break

    logger.info(
        f"Scan complete: {total_scanned:,} total, "
        f"{len(needing_explanation):,} need explanations, "
        f"{skipped_has_explanation:,} already have explanations, "
        f"{skipped_commencement:,} commencement orders skipped"
    )
    return needing_explanation


def fetch_amendments_with_explanations(
    batch_size: int = 1000, limit: int | None = None
) -> list[Amendment]:
    """Scroll all amendments that have explanations (for re-embedding)."""
    logger.info(f"Scanning {AMENDMENT_COLLECTION} for amendments with explanations...")

    with_explanations = []
    total_scanned = 0
    offset = None

    while True:
        results, next_offset = qdrant_client.scroll(
            collection_name=AMENDMENT_COLLECTION,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            break

        for point in results:
            total_scanned += 1
            if point.payload.get("ai_explanation"):
                with_explanations.append(Amendment(**point.payload))
                if limit and len(with_explanations) >= limit:
                    break

        if total_scanned % 100_000 == 0:
            logger.info(f"Scanned {total_scanned:,}... ({len(with_explanations):,} with explanations)")

        if limit and len(with_explanations) >= limit:
            break

        offset = next_offset
        if offset is None:
            break

    logger.info(f"Found {len(with_explanations):,} amendments with explanations")
    return with_explanations


def run_phase_1(
    amendments: list[Amendment],
    workers: int = 200,
    batch_size: int = 100,
    dry_run: bool = True,
) -> int:
    """Phase 1: Generate explanations and update Qdrant payloads."""
    console.rule("Phase 1: Generate Explanations")
    logger.info(f"Processing {len(amendments):,} amendments with {workers} workers")

    if dry_run:
        logger.info(f"[DRY RUN] Would generate explanations for {len(amendments):,} amendments")
        return 0

    completed = 0
    failed = 0
    start_time = time.time()

    # Process in batches for Qdrant payload updates
    for batch_start in range(0, len(amendments), batch_size):
        batch = amendments[batch_start : batch_start + batch_size]
        batch_operations = []

        # Generate explanations in parallel
        with ThreadPoolExecutor(max_workers=min(workers, len(batch))) as executor:
            future_to_amendment = {
                executor.submit(generate_explanation, amendment): amendment
                for amendment in batch
            }

            for future in as_completed(future_to_amendment):
                amendment = future_to_amendment[future]
                try:
                    explanation, model_used, timestamp = future.result()

                    # Skip error explanations
                    if explanation.startswith("Error generating explanation:"):
                        failed += 1
                        continue

                    # Build set_payload operation
                    point_id = str(uri_to_uuid(amendment.id))
                    operation = models.SetPayloadOperation(
                        set_payload=models.SetPayload(
                            payload={
                                "ai_explanation": explanation,
                                "ai_explanation_model": model_used,
                                "ai_explanation_timestamp": timestamp.isoformat(),
                            },
                            points=[point_id],
                        )
                    )
                    batch_operations.append(operation)
                    completed += 1

                except Exception as e:
                    logger.error(f"Failed for {amendment.id}: {e}")
                    failed += 1

        # Flush batch to Qdrant
        if batch_operations:
            try:
                qdrant_client.batch_update_points(
                    collection_name=AMENDMENT_COLLECTION,
                    update_operations=batch_operations,
                    wait=False,
                )
            except Exception as e:
                logger.error(f"Batch update failed: {e}")
                failed += len(batch_operations)
                completed -= len(batch_operations)

        elapsed = time.time() - start_time
        rate = completed / elapsed * 60 if elapsed > 0 else 0
        total_processed = completed + failed
        remaining = len(amendments) - total_processed
        eta_minutes = remaining / rate if rate > 0 else 0

        logger.info(
            f"Progress: {total_processed:,}/{len(amendments):,} "
            f"({completed:,} ok, {failed:,} failed) "
            f"| {rate:.0f}/min | ETA: {eta_minutes:.0f}min"
        )

    return completed


def run_phase_2(
    amendments: list[Amendment],
    embedding_workers: int = 50,
    batch_size: int = 100,
    dry_run: bool = True,
) -> int:
    """Phase 2: Re-embed amendments with explanations and upsert."""
    console.rule("Phase 2: Re-embed Amendments")
    logger.info(f"Re-embedding {len(amendments):,} amendments with {embedding_workers} embedding workers")

    if dry_run:
        logger.info(f"[DRY RUN] Would re-embed {len(amendments):,} amendments")
        return 0

    uploaded = 0
    start_time = time.time()

    for batch_start in range(0, len(amendments), batch_size):
        batch = amendments[batch_start : batch_start + batch_size]
        texts = [a.get_embedding_text() for a in batch]

        try:
            embeddings = generate_hybrid_embeddings_batch(
                texts, max_workers=embedding_workers
            )

            points = []
            for amendment, (dense, sparse) in zip(batch, embeddings):
                point_id = str(uri_to_uuid(amendment.id))
                points.append(
                    PointStruct(
                        id=point_id,
                        vector={"dense": dense, "sparse": sparse},
                        payload=amendment.model_dump(mode="json"),
                    )
                )

            qdrant_client.upsert(collection_name=AMENDMENT_COLLECTION, points=points)
            uploaded += len(points)

            elapsed = time.time() - start_time
            rate = uploaded / elapsed * 60 if elapsed > 0 else 0
            remaining = len(amendments) - uploaded
            eta_minutes = remaining / rate if rate > 0 else 0

            logger.info(
                f"Embedded: {uploaded:,}/{len(amendments):,} "
                f"| {rate:.0f}/min | ETA: {eta_minutes:.0f}min"
            )

        except Exception as e:
            logger.error(f"Embedding batch failed at offset {batch_start}: {e}")
            continue

    return uploaded


def main():
    parser = argparse.ArgumentParser(description="Backfill AI explanations for amendments")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit number of amendments to process (for testing)",
    )
    parser.add_argument(
        "--explanation-workers", type=int, default=200,
        help="Concurrent workers for explanation generation (default: 200)",
    )
    parser.add_argument(
        "--embedding-workers", type=int, default=50,
        help="Concurrent workers for embedding generation (default: 50)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100,
        help="Batch size for Qdrant operations (default: 100)",
    )
    parser.add_argument(
        "--phase", choices=["1", "2", "both"], default="both",
        help="Which phase to run: 1 (explanations), 2 (re-embed), both (default: both)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply changes (default: dry run)",
    )

    args = parser.parse_args()
    setup_logging()
    dry_run = not args.apply

    start_time = time.time()
    print_header(
        "Amendment Explanation Backfill",
        mode="APPLY" if args.apply else "DRY RUN",
        details={
            "Phase": args.phase,
            "Limit": str(args.limit or "ALL"),
            "Explanation workers": str(args.explanation_workers),
            "Embedding workers": str(args.embedding_workers),
            "Batch size": str(args.batch_size),
        },
    )

    explained_count = 0
    embedded_count = 0

    # Phase 1: Generate explanations
    if args.phase in ("1", "both"):
        amendments = fetch_amendments_needing_explanation(limit=args.limit)
        if amendments:
            explained_count = run_phase_1(
                amendments,
                workers=args.explanation_workers,
                batch_size=args.batch_size,
                dry_run=dry_run,
            )
        else:
            logger.info("No amendments need explanations")

    # Phase 2: Re-embed
    if args.phase in ("2", "both"):
        amendments_to_embed = fetch_amendments_with_explanations(limit=args.limit)
        if amendments_to_embed:
            embedded_count = run_phase_2(
                amendments_to_embed,
                embedding_workers=args.embedding_workers,
                batch_size=args.batch_size,
                dry_run=dry_run,
            )
        else:
            logger.info("No amendments with explanations to re-embed")

    # Verify
    if args.apply:
        total = qdrant_client.count(collection_name=AMENDMENT_COLLECTION, exact=False)
        logger.info(f"Collection points: {total.count:,}")

    total_time = time.time() - start_time
    print_summary(
        "Backfill Complete",
        {
            "Total time": f"{total_time:.0f}s ({total_time / 60:.1f} minutes)",
            "Explanations generated": str(explained_count),
            "Amendments re-embedded": str(embedded_count),
        },
        success=True,
    )


if __name__ == "__main__":
    main()
