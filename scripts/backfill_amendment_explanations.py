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
import json
import logging
import os
import random
import sys
import threading
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
    fetch_provision_text,
    get_openai_client,
)
from lex.core.uri import normalise_legislation_uri
from lex.settings import AMENDMENT_COLLECTION, LEGISLATION_SECTION_COLLECTION

logger = logging.getLogger(__name__)
qdrant_client = get_qdrant_client()

# Thread-safe counters for Qdrant lookup stats
_stats_lock = threading.Lock()
_qdrant_hits = 0
_http_fallbacks = 0
_total_misses = 0

PROGRESS_FILE_PHASE_1 = "/tmp/backfill_progress_phase1.json"
PROGRESS_FILE_PHASE_2 = "/tmp/backfill_progress_phase2.json"


def _write_progress(data: dict, phase: int = 1) -> None:
    """Atomically write progress data to JSON file."""
    progress_file = PROGRESS_FILE_PHASE_1 if phase == 1 else PROGRESS_FILE_PHASE_2
    tmp = progress_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, progress_file)

PROVISION_TYPES = {
    "section", "schedule", "regulation", "article", "rule", "part", "chapter",
    "paragraph", "crossheading",
}


def extract_parent_section_uri(provision_url: str) -> str | None:
    """Extract the top-level section/schedule URI from a fine-grained provision URL.

    E.g. http://www.legislation.gov.uk/id/ukpga/2024/1/section/5/2/a
      -> http://www.legislation.gov.uk/id/ukpga/2024/1/section/5
    """
    parts = provision_url.split("/")
    # Canonical form: ['http:', '', 'www.legislation.gov.uk', 'id', type, year, number, prov_type, prov_num, ...]
    # We need at least 9 parts (indices 0-8)
    if len(parts) < 9:
        return None

    # Find the first provision type segment after the legislation identifier
    # (parts[7] should be section/schedule/regulation/etc.)
    if parts[7].lower() not in PROVISION_TYPES:
        return None

    return "/".join(parts[:9])


def fetch_provision_text_from_qdrant(provision_url: str) -> str | None:
    """Look up provision text from the legislation_section Qdrant collection.

    Extracts the parent section URI, converts to a point ID, and retrieves
    the text payload. Returns None if not found.
    """
    normalised = normalise_legislation_uri(provision_url)
    parent_uri = extract_parent_section_uri(normalised)
    if not parent_uri:
        return None

    point_id = str(uri_to_uuid(parent_uri))
    try:
        points = qdrant_client.retrieve(
            collection_name=LEGISLATION_SECTION_COLLECTION,
            ids=[point_id],
            with_payload=True,
            with_vectors=False,
        )
        if points:
            text = points[0].payload.get("text", "")
            if text:
                # Truncate to 8000 chars to match fetch_provision_text behaviour
                if len(text) > 8000:
                    text = text[:8000] + "... [truncated]"
                return text
    except Exception as e:
        logger.debug(f"Qdrant lookup failed for {parent_uri}: {e}")

    return None


def _fetch_with_fallback(
    provision_url: str,
    http_semaphore: threading.Semaphore,
) -> str | None:
    """Fetch provision text: Qdrant first, HTTP fallback."""
    global _qdrant_hits, _http_fallbacks, _total_misses

    # Try Qdrant first (no semaphore needed - instant)
    text = fetch_provision_text_from_qdrant(provision_url)
    if text:
        with _stats_lock:
            _qdrant_hits += 1
        return text

    # Fall back to HTTP fetch (with semaphore)
    with http_semaphore:
        text = fetch_provision_text(provision_url)
    if text:
        with _stats_lock:
            _http_fallbacks += 1
        return text

    with _stats_lock:
        _total_misses += 1
    return None


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
    batch_size: int = 10000, limit: int | None = None
) -> list[Amendment]:
    """Scroll amendments that have explanations, using server-side filter."""
    logger.info(f"Scanning {AMENDMENT_COLLECTION} for amendments with explanations...")

    explanation_filter = models.Filter(
        must_not=[
            models.IsEmptyCondition(
                is_empty=models.PayloadField(key="ai_explanation"),
            ),
            models.IsNullCondition(
                is_null=models.PayloadField(key="ai_explanation"),
            ),
        ],
    )

    with_explanations = []
    offset = None

    while True:
        results, next_offset = qdrant_client.scroll(
            collection_name=AMENDMENT_COLLECTION,
            scroll_filter=explanation_filter,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            break

        for point in results:
            with_explanations.append(Amendment(**point.payload))
            if limit and len(with_explanations) >= limit:
                break

        if len(with_explanations) % 10_000 < batch_size:
            logger.info(f"Fetched {len(with_explanations):,} with explanations so far...")

        if limit and len(with_explanations) >= limit:
            break

        offset = next_offset
        if offset is None:
            break

    logger.info(f"Found {len(with_explanations):,} amendments with explanations")
    return with_explanations


def _throttled_generate(
    amendment: Amendment,
    http_semaphore: threading.Semaphore,
) -> tuple[str, str, datetime]:
    """Generate explanation with throttled HTTP access.

    The semaphore limits concurrent legislation.gov.uk requests to avoid
    thundering herd when 200 threads all retry simultaneously.
    GPT-5-nano calls happen outside the semaphore (effectively unlimited).
    """
    changed_text = None
    if amendment.changed_provision_url:
        changed_text = _fetch_with_fallback(amendment.changed_provision_url, http_semaphore)

    affecting_text = None
    if amendment.affecting_provision_url:
        affecting_text = _fetch_with_fallback(amendment.affecting_provision_url, http_semaphore)

    # Build prompt (same as generate_explanation)
    prompt = f"""Analyze this UK legislative amendment concisely and clearly.

Amendment Details:
- Changed Legislation: {amendment.changed_legislation}
- Changed Provision: {amendment.changed_provision or "N/A"}
- Affecting Legislation: {amendment.affecting_legislation or "N/A"}
- Affecting Provision: {amendment.affecting_provision or "N/A"}
- Type of Effect: {amendment.type_of_effect or "N/A"}

Changed Provision Text (current version):
{changed_text if changed_text else "[Not available - provision may not exist or have been repealed]"}

Affecting Provision Text (the instruction that makes the change):
{affecting_text if affecting_text else "[Not available]"}

Provide a 3-part explanation:
(1) Legal change - what was added, removed, or modified (be specific and brief)
(2) Practical impact - real-world consequences for courts, agencies, or individuals (focus on key effects)
(3) Plain language - restate for non-lawyers (use clear language, expand acronyms on first use, avoid unnecessary jargon)

Write densely and efficiently. Favor clarity over length. Keep each part to 1-2 concise sentences."""

    # GPT-5-nano call outside semaphore (no HTTP throttling needed)
    openai_client = get_openai_client()
    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5-nano")

    response = openai_client.responses.create(
        model=deployment,
        input=prompt,
        reasoning={"effort": "low"},
        text={"verbosity": "low"},
    )

    return response.output_text.strip(), deployment, datetime.now(timezone.utc)


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

    global _qdrant_hits, _http_fallbacks, _total_misses
    _qdrant_hits = _http_fallbacks = _total_misses = 0

    completed = 0
    failed = 0
    start_time = time.time()

    # Limit concurrent HTTP requests to legislation.gov.uk
    # Qdrant fallback handles ~76% of lookups, so fewer requests hit HTTP
    http_semaphore = threading.Semaphore(25)

    buffer = []  # Accumulates SetPayload operations, flushed every batch_size
    flush_count = 0

    # Single executor, submit all work upfront — no batch-and-wait
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_throttled_generate, amendment, http_semaphore): amendment
            for amendment in amendments
        }

        for future in as_completed(futures):
            amendment = futures[future]
            try:
                explanation, model_used, timestamp = future.result()

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
                buffer.append(operation)
                completed += 1

            except Exception as e:
                logger.error(f"Failed for {amendment.id}: {e}")
                failed += 1

            # Flush buffer every batch_size completions
            if len(buffer) >= batch_size:
                try:
                    qdrant_client.batch_update_points(
                        collection_name=AMENDMENT_COLLECTION,
                        update_operations=buffer,
                        wait=False,
                    )
                except Exception as e:
                    logger.error(f"Batch update failed: {e}")
                    failed += len(buffer)
                    completed -= len(buffer)
                buffer = []
                flush_count += 1

                elapsed = time.time() - start_time
                rate = completed / elapsed * 60 if elapsed > 0 else 0
                total_processed = completed + failed
                remaining = len(amendments) - total_processed
                eta_minutes = remaining / rate if rate > 0 else 0

                logger.info(
                    f"Progress: {total_processed:,}/{len(amendments):,} "
                    f"({completed:,} ok, {failed:,} failed) "
                    f"| {rate:.0f}/min | ETA: {eta_minutes:.0f}min "
                    f"| Qdrant: {_qdrant_hits:,} HTTP: {_http_fallbacks:,} miss: {_total_misses:,}"
                )

                _write_progress({
                    "phase": 1,
                    "flush": flush_count,
                    "completed": completed,
                    "failed": failed,
                    "total_amendments": len(amendments),
                    "qdrant_hits": _qdrant_hits,
                    "http_fallbacks": _http_fallbacks,
                    "misses": _total_misses,
                    "rate_per_min": round(rate, 1),
                    "eta_minutes": round(eta_minutes, 1),
                    "elapsed_seconds": round(elapsed),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    # Flush remaining buffer
    if buffer:
        try:
            qdrant_client.batch_update_points(
                collection_name=AMENDMENT_COLLECTION,
                update_operations=buffer,
                wait=False,
            )
        except Exception as e:
            logger.error(f"Final batch update failed: {e}")
            failed += len(buffer)
            completed -= len(buffer)

        elapsed = time.time() - start_time
        rate = completed / elapsed * 60 if elapsed > 0 else 0
        logger.info(
            f"Final: {completed + failed:,}/{len(amendments):,} "
            f"({completed:,} ok, {failed:,} failed) "
            f"| {rate:.0f}/min "
            f"| Qdrant: {_qdrant_hits:,} HTTP: {_http_fallbacks:,} miss: {_total_misses:,}"
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
    total_batches = (len(amendments) + batch_size - 1) // batch_size

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

            qdrant_client.upsert(collection_name=AMENDMENT_COLLECTION, points=points, wait=False)
            uploaded += len(points)

            elapsed = time.time() - start_time
            rate = uploaded / elapsed * 60 if elapsed > 0 else 0
            remaining = len(amendments) - uploaded
            eta_minutes = remaining / rate if rate > 0 else 0

            logger.info(
                f"Embedded: {uploaded:,}/{len(amendments):,} "
                f"| {rate:.0f}/min | ETA: {eta_minutes:.0f}min"
            )

            _write_progress({
                "phase": 2,
                "batch": batch_start // batch_size + 1,
                "total_batches": total_batches,
                "uploaded": uploaded,
                "total_amendments": len(amendments),
                "rate_per_min": round(rate, 1),
                "eta_minutes": round(eta_minutes, 1),
                "elapsed_seconds": round(elapsed),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, phase=2)

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
    total_lookups = _qdrant_hits + _http_fallbacks + _total_misses
    qdrant_pct = (_qdrant_hits / total_lookups * 100) if total_lookups > 0 else 0
    print_summary(
        "Backfill Complete",
        {
            "Total time": f"{total_time:.0f}s ({total_time / 60:.1f} minutes)",
            "Explanations generated": str(explained_count),
            "Amendments re-embedded": str(embedded_count),
            "Provision lookups": f"{total_lookups:,} (Qdrant: {_qdrant_hits:,} [{qdrant_pct:.0f}%], HTTP: {_http_fallbacks:,}, miss: {_total_misses:,})",
        },
        success=True,
    )


if __name__ == "__main__":
    main()
