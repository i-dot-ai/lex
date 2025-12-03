"""Orchestrator for unified ingestion pipeline.

Coordinates the two-stage DAG:
    Stage 1: Scrape sources (parallel)
        - Caselaw unified (core + sections)
        - Legislation unified (core + sections)
        - Amendments

    Stage 2: AI enrichment (parallel, after Stage 1)
        - Caselaw summaries
        - Explanatory notes
"""

import asyncio
import gc
import logging
from datetime import date

from qdrant_client.models import PointStruct

from lex.caselaw.models import Caselaw, CaselawSection, CaselawSummary, Court
from lex.caselaw.pipeline import pipe_caselaw_summaries, pipe_caselaw_unified
from lex.caselaw.qdrant_schema import (
    get_caselaw_schema,
    get_caselaw_section_schema,
    get_caselaw_summary_schema,
)
from lex.core.embeddings import generate_hybrid_embeddings
from lex.core.qdrant_client import qdrant_client
from lex.core.utils import create_collection_if_none
from lex.legislation.models import Legislation, LegislationSection, LegislationType
from lex.legislation.pipeline import pipe_legislation_unified
from lex.legislation.qdrant_schema import (
    get_legislation_schema,
    get_legislation_section_schema,
)
from lex.settings import (
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    CASELAW_SUMMARY_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

logger = logging.getLogger(__name__)

# Batch size for Qdrant uploads
BATCH_SIZE = 100


async def run_daily_ingest(
    limit: int | None = None,
    enable_pdf_fallback: bool = False,
    enable_summaries: bool = False,
) -> dict:
    """Run daily incremental ingest.

    Ingests data from the current and previous year to catch any updates.

    Args:
        limit: Maximum number of items per source (None for unlimited)
        enable_pdf_fallback: Enable PDF processing for legislation without XML
        enable_summaries: Enable AI summary generation (Stage 2)

    Returns:
        Statistics about the ingest run
    """
    years = [date.today().year, date.today().year - 1]
    logger.info(f"Starting daily ingest for years {years}, limit={limit}")

    stats = {}

    # Stage 1: Scrape sources (run in parallel using asyncio)
    stage1_results = await asyncio.gather(
        asyncio.to_thread(ingest_caselaw, years, limit),
        asyncio.to_thread(ingest_legislation, years, limit, enable_pdf_fallback),
        return_exceptions=True,
    )

    if isinstance(stage1_results[0], Exception):
        stats["caselaw"] = {"error": str(stage1_results[0])}
    else:
        stats["caselaw"] = stage1_results[0]

    if isinstance(stage1_results[1], Exception):
        stats["legislation"] = {"error": str(stage1_results[1])}
    else:
        stats["legislation"] = stage1_results[1]

    # Stage 2: AI enrichment (after Stage 1 completes)
    if enable_summaries:
        stage2_results = await asyncio.gather(
            asyncio.to_thread(ingest_caselaw_summaries, years, limit),
            return_exceptions=True,
        )
        if isinstance(stage2_results[0], Exception):
            logger.error(f"Caselaw summary generation failed: {stage2_results[0]}")
            stats["caselaw_summaries"] = {"error": str(stage2_results[0])}
        else:
            stats["caselaw_summaries"] = stage2_results[0]

    logger.info(f"Daily ingest complete: {stats}")
    return stats


async def run_full_ingest(
    years: list[int] | None = None,
    limit: int | None = None,
    enable_pdf_fallback: bool = False,
    enable_summaries: bool = False,
) -> dict:
    """Run full historical ingest.

    Args:
        years: List of years to ingest (defaults to 1963-current)
        limit: Maximum number of items per source (None for unlimited)
        enable_pdf_fallback: Enable PDF processing for legislation without XML
        enable_summaries: Enable AI summary generation (Stage 2)

    Returns:
        Statistics about the ingest run
    """
    if years is None:
        years = list(range(1963, date.today().year + 1))

    logger.info(f"Starting full ingest for {len(years)} years, limit={limit}")

    stats = {}

    # Stage 1: Scrape sources (sequential for full ingest to manage resources)
    stats["caselaw"] = ingest_caselaw(years, limit)
    stats["legislation"] = ingest_legislation(years, limit, enable_pdf_fallback)

    # Stage 2: AI enrichment (after Stage 1 completes)
    if enable_summaries:
        try:
            stats["caselaw_summaries"] = ingest_caselaw_summaries(years, limit)
        except Exception as e:
            logger.error(f"Caselaw summary generation failed: {e}")
            stats["caselaw_summaries"] = {"error": str(e)}

    logger.info(f"Full ingest complete: {stats}")
    return stats


def ingest_caselaw(years: list[int], limit: int | None = None) -> dict:
    """Ingest caselaw using the unified pipeline.

    Args:
        years: List of years to process
        limit: Maximum number of items (None for unlimited)

    Returns:
        Statistics about the ingest
    """
    logger.info(f"Starting caselaw ingest: years={years}, limit={limit}")

    # Ensure collections exist
    create_collection_if_none(
        CASELAW_COLLECTION,
        get_caselaw_schema(),
        non_interactive=True,
    )
    create_collection_if_none(
        CASELAW_SECTION_COLLECTION,
        get_caselaw_section_schema(),
        non_interactive=True,
    )

    stats = {
        "caselaw_count": 0,
        "section_count": 0,
        "errors": 0,
    }

    # Batches for each collection
    caselaw_batch: list[PointStruct] = []
    section_batch: list[PointStruct] = []

    courts = list(Court)
    pipeline = pipe_caselaw_unified(years=years, limit=limit, types=courts)

    for collection_type, doc in pipeline:
        try:
            point = _create_point(doc)

            if collection_type == "caselaw":
                caselaw_batch.append(point)
                stats["caselaw_count"] += 1

                if len(caselaw_batch) >= BATCH_SIZE:
                    _upload_batch(CASELAW_COLLECTION, caselaw_batch)
                    caselaw_batch = []
                    gc.collect()

            elif collection_type == "caselaw-section":
                section_batch.append(point)
                stats["section_count"] += 1

                if len(section_batch) >= BATCH_SIZE:
                    _upload_batch(CASELAW_SECTION_COLLECTION, section_batch)
                    section_batch = []

        except Exception as e:
            logger.warning(f"Failed to process {collection_type} document: {e}")
            stats["errors"] += 1

    # Upload remaining batches
    if caselaw_batch:
        _upload_batch(CASELAW_COLLECTION, caselaw_batch)
    if section_batch:
        _upload_batch(CASELAW_SECTION_COLLECTION, section_batch)

    logger.info(f"Caselaw ingest complete: {stats}")
    return stats


def ingest_legislation(
    years: list[int],
    limit: int | None = None,
    enable_pdf_fallback: bool = False,
) -> dict:
    """Ingest legislation using the unified pipeline.

    Args:
        years: List of years to process
        limit: Maximum number of items (None for unlimited)
        enable_pdf_fallback: Enable PDF processing for legislation without XML

    Returns:
        Statistics about the ingest
    """
    logger.info(
        f"Starting legislation ingest: years={years}, limit={limit}, "
        f"pdf_fallback={enable_pdf_fallback}"
    )

    # Ensure collections exist
    create_collection_if_none(
        LEGISLATION_COLLECTION,
        get_legislation_schema(),
        non_interactive=True,
    )
    create_collection_if_none(
        LEGISLATION_SECTION_COLLECTION,
        get_legislation_section_schema(),
        non_interactive=True,
    )

    stats = {
        "legislation_count": 0,
        "section_count": 0,
        "errors": 0,
    }

    # Batches for each collection
    legislation_batch: list[PointStruct] = []
    section_batch: list[PointStruct] = []

    types = list(LegislationType)
    pipeline = pipe_legislation_unified(
        years=years,
        limit=limit,
        types=types,
        enable_pdf_fallback=enable_pdf_fallback,
    )

    for collection_type, doc in pipeline:
        try:
            point = _create_point(doc)

            if collection_type == "legislation":
                legislation_batch.append(point)
                stats["legislation_count"] += 1

                if len(legislation_batch) >= BATCH_SIZE:
                    _upload_batch(LEGISLATION_COLLECTION, legislation_batch)
                    legislation_batch = []
                    gc.collect()

            elif collection_type == "legislation-section":
                section_batch.append(point)
                stats["section_count"] += 1

                if len(section_batch) >= BATCH_SIZE:
                    _upload_batch(LEGISLATION_SECTION_COLLECTION, section_batch)
                    section_batch = []

        except Exception as e:
            logger.warning(f"Failed to process {collection_type} document: {e}")
            stats["errors"] += 1

    # Upload remaining batches
    if legislation_batch:
        _upload_batch(LEGISLATION_COLLECTION, legislation_batch)
    if section_batch:
        _upload_batch(LEGISLATION_SECTION_COLLECTION, section_batch)

    logger.info(f"Legislation ingest complete: {stats}")
    return stats


def ingest_caselaw_summaries(
    years: list[int],
    limit: int | None = None,
) -> dict:
    """Generate AI summaries for caselaw documents (Stage 2).

    Queries the caselaw collection for documents matching the criteria,
    filters out those that already have summaries, generates summaries
    for the rest, and uploads them to Qdrant.

    Args:
        years: Years to process
        limit: Maximum number of summaries to generate

    Returns:
        Statistics about the ingest
    """
    logger.info(f"Starting caselaw summary generation: years={years}, limit={limit}")

    # Ensure summary collection exists
    create_collection_if_none(
        CASELAW_SUMMARY_COLLECTION,
        get_caselaw_summary_schema(),
        non_interactive=True,
    )

    stats = {
        "summary_count": 0,
        "errors": 0,
    }

    summary_batch: list[PointStruct] = []
    courts = list(Court)

    # pipe_caselaw_summaries treats 0/falsy as unlimited
    pipeline = pipe_caselaw_summaries(
        years=years,
        limit=limit or 0,
        types=courts,
    )

    for summary in pipeline:
        try:
            point = _create_point(summary)
            summary_batch.append(point)
            stats["summary_count"] += 1

            if len(summary_batch) >= BATCH_SIZE:
                _upload_batch(CASELAW_SUMMARY_COLLECTION, summary_batch)
                summary_batch = []
                gc.collect()

        except Exception as e:
            logger.warning(f"Failed to process caselaw summary: {e}")
            stats["errors"] += 1

    # Upload remaining batch
    if summary_batch:
        _upload_batch(CASELAW_SUMMARY_COLLECTION, summary_batch)

    logger.info(f"Caselaw summary generation complete: {stats}")
    return stats


def _create_point(
    doc: Caselaw | CaselawSection | CaselawSummary | Legislation | LegislationSection,
) -> PointStruct:
    """Create a Qdrant PointStruct from a document.

    Args:
        doc: Document with id, get_embedding_text(), and model_dump() methods

    Returns:
        PointStruct ready for upload
    """
    from lex.core.document import uri_to_uuid

    embedding_text = doc.get_embedding_text()
    dense, sparse = generate_hybrid_embeddings(embedding_text)

    return PointStruct(
        id=uri_to_uuid(doc.id),
        vector={"dense": dense, "sparse": sparse},
        payload=doc.model_dump(mode="json"),
    )


def _upload_batch(collection: str, batch: list[PointStruct]) -> None:
    """Upload a batch of points to Qdrant.

    Args:
        collection: Collection name
        batch: List of PointStructs to upload
    """
    if not batch:
        return

    try:
        qdrant_client.upsert(
            collection_name=collection,
            points=batch,
            wait=True,
        )
        logger.debug(f"Uploaded {len(batch)} points to {collection}")
    except Exception as e:
        logger.error(f"Failed to upload batch to {collection}: {e}")
        raise
