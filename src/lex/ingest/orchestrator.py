"""Orchestrator for unified ingestion pipeline.

Coordinates the two-stage DAG:
    Stage 1: Scrape sources (parallel)
        - Caselaw unified (core + sections)
        - Legislation unified (core + sections)
        - Amendments
        - Explanatory notes

    Stage 2: AI enrichment (parallel, after Stage 1)
        - Caselaw summaries
"""

import asyncio
import gc
import logging
from datetime import date

from qdrant_client.models import PointStruct

from lex.amendment.pipeline import pipe_amendments
from lex.amendment.qdrant_schema import get_amendment_schema
from lex.caselaw.models import Court
from lex.caselaw.pipeline import pipe_caselaw_summaries, pipe_caselaw_unified
from lex.caselaw.qdrant_schema import (
    get_caselaw_schema,
    get_caselaw_section_schema,
    get_caselaw_summary_schema,
)
from lex.core.embeddings import generate_hybrid_embeddings_batch
from lex.core.qdrant_client import qdrant_client
from lex.core.utils import create_collection_if_none
from lex.explanatory_note.pipeline import pipe_explanatory_note
from lex.explanatory_note.qdrant_schema import get_explanatory_note_schema
from lex.ingest.amendments_led import (
    get_changed_legislation_ids,
    get_stale_or_missing_legislation_ids,
    parse_legislation_id,
)
from lex.legislation.models import LegislationType
from lex.legislation.pipeline import pipe_legislation_unified
from lex.legislation.qdrant_schema import (
    get_legislation_schema,
    get_legislation_section_schema,
)
from lex.settings import (
    AMENDMENT_COLLECTION,
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    CASELAW_SUMMARY_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

logger = logging.getLogger(__name__)

# Batch size for Qdrant uploads (keep small to avoid exceeding Qdrant's 32MB payload limit)
# Some legislation sections are very large (~3MB each), so use small batches
BATCH_SIZE = 10


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
    # Note: caselaw ingest disabled - caselaw API has been taken down
    stage1_results = await asyncio.gather(
        asyncio.to_thread(ingest_legislation, years, limit, enable_pdf_fallback),
        asyncio.to_thread(ingest_amendments, years, limit),
        asyncio.to_thread(ingest_explanatory_notes, years, limit),
        return_exceptions=True,
    )

    if isinstance(stage1_results[0], Exception):
        stats["legislation"] = {"error": str(stage1_results[0])}
    else:
        stats["legislation"] = stage1_results[0]

    if isinstance(stage1_results[1], Exception):
        stats["amendments"] = {"error": str(stage1_results[1])}
    else:
        stats["amendments"] = stage1_results[1]

    if isinstance(stage1_results[2], Exception):
        stats["explanatory_notes"] = {"error": str(stage1_results[2])}
    else:
        stats["explanatory_notes"] = stage1_results[2]

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
    # Note: caselaw ingest disabled - caselaw API has been taken down
    stats["legislation"] = ingest_legislation(years, limit, enable_pdf_fallback)
    stats["amendments"] = ingest_amendments(years, limit)
    stats["explanatory_notes"] = ingest_explanatory_notes(years, limit)

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

    # Collect docs, then batch embed when ready
    caselaw_docs: list = []
    section_docs: list = []

    courts = list(Court)
    pipeline = pipe_caselaw_unified(years=years, limit=limit, types=courts)

    for collection_type, doc in pipeline:
        try:
            if collection_type == "caselaw":
                caselaw_docs.append(doc)
                stats["caselaw_count"] += 1

                if len(caselaw_docs) >= BATCH_SIZE:
                    points = _create_points_batch(caselaw_docs)
                    _upload_batch(CASELAW_COLLECTION, points)
                    caselaw_docs = []
                    gc.collect()

            elif collection_type == "caselaw-section":
                section_docs.append(doc)
                stats["section_count"] += 1

                if len(section_docs) >= BATCH_SIZE:
                    points = _create_points_batch(section_docs)
                    _upload_batch(CASELAW_SECTION_COLLECTION, points)
                    section_docs = []

        except Exception as e:
            logger.warning(f"Failed to process {collection_type} document: {e}")
            stats["errors"] += 1

    # Upload remaining docs
    if caselaw_docs:
        points = _create_points_batch(caselaw_docs)
        _upload_batch(CASELAW_COLLECTION, points)
    if section_docs:
        points = _create_points_batch(section_docs)
        _upload_batch(CASELAW_SECTION_COLLECTION, points)

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

    # Collect docs, then batch embed when ready
    legislation_docs: list = []
    section_docs: list = []

    types = list(LegislationType)
    pipeline = pipe_legislation_unified(
        years=years,
        limit=limit,
        types=types,
        enable_pdf_fallback=enable_pdf_fallback,
    )

    for collection_type, doc in pipeline:
        try:
            if collection_type == "legislation":
                legislation_docs.append(doc)
                stats["legislation_count"] += 1

                if len(legislation_docs) >= BATCH_SIZE:
                    points = _create_points_batch(legislation_docs)
                    _upload_batch(LEGISLATION_COLLECTION, points)
                    legislation_docs = []
                    gc.collect()

            elif collection_type == "legislation-section":
                section_docs.append(doc)
                stats["section_count"] += 1

                if len(section_docs) >= BATCH_SIZE:
                    points = _create_points_batch(section_docs)
                    _upload_batch(LEGISLATION_SECTION_COLLECTION, points)
                    section_docs = []

        except Exception as e:
            logger.warning(f"Failed to process {collection_type} document: {e}")
            stats["errors"] += 1

    # Upload remaining docs
    if legislation_docs:
        points = _create_points_batch(legislation_docs)
        _upload_batch(LEGISLATION_COLLECTION, points)
    if section_docs:
        points = _create_points_batch(section_docs)
        _upload_batch(LEGISLATION_SECTION_COLLECTION, points)

    logger.info(f"Legislation ingest complete: {stats}")
    return stats


def ingest_amendments(years: list[int], limit: int | None = None) -> dict:
    """Ingest amendments using the amendments pipeline.

    Args:
        years: List of years to process
        limit: Maximum number of items (None for unlimited)

    Returns:
        Statistics about the ingest
    """
    logger.info(f"Starting amendments ingest: years={years}, limit={limit}")

    # Ensure collection exists
    create_collection_if_none(
        AMENDMENT_COLLECTION,
        get_amendment_schema(),
        non_interactive=True,
    )

    stats = {
        "amendment_count": 0,
        "errors": 0,
    }

    amendment_docs: list = []
    pipeline = pipe_amendments(years=years, limit=limit or 0)

    for amendment in pipeline:
        try:
            amendment_docs.append(amendment)
            stats["amendment_count"] += 1

            if len(amendment_docs) >= BATCH_SIZE:
                points = _create_points_batch(amendment_docs)
                _upload_batch(AMENDMENT_COLLECTION, points)
                amendment_docs = []
                gc.collect()

        except Exception as e:
            logger.warning(f"Failed to process amendment: {e}")
            stats["errors"] += 1

    # Upload remaining docs
    if amendment_docs:
        points = _create_points_batch(amendment_docs)
        _upload_batch(AMENDMENT_COLLECTION, points)

    logger.info(f"Amendments ingest complete: {stats}")
    return stats


def ingest_explanatory_notes(years: list[int], limit: int | None = None) -> dict:
    """Ingest explanatory notes using the explanatory notes pipeline.

    Args:
        years: List of years to process
        limit: Maximum number of items (None for unlimited)

    Returns:
        Statistics about the ingest
    """
    logger.info(f"Starting explanatory notes ingest: years={years}, limit={limit}")

    # Ensure collection exists
    create_collection_if_none(
        EXPLANATORY_NOTE_COLLECTION,
        get_explanatory_note_schema(),
        non_interactive=True,
    )

    stats = {
        "explanatory_note_count": 0,
        "errors": 0,
    }

    note_docs: list = []
    types = list(LegislationType)
    pipeline = pipe_explanatory_note(years=years, types=types, limit=limit)

    for note in pipeline:
        try:
            note_docs.append(note)
            stats["explanatory_note_count"] += 1

            if len(note_docs) >= BATCH_SIZE:
                points = _create_points_batch(note_docs)
                _upload_batch(EXPLANATORY_NOTE_COLLECTION, points)
                note_docs = []
                gc.collect()

        except Exception as e:
            logger.warning(f"Failed to process explanatory note: {e}")
            stats["errors"] += 1

    # Upload remaining docs
    if note_docs:
        points = _create_points_batch(note_docs)
        _upload_batch(EXPLANATORY_NOTE_COLLECTION, points)

    logger.info(f"Explanatory notes ingest complete: {stats}")
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

    summary_docs: list = []
    courts = list(Court)

    # pipe_caselaw_summaries treats 0/falsy as unlimited
    pipeline = pipe_caselaw_summaries(
        years=years,
        limit=limit or 0,
        types=courts,
    )

    for summary in pipeline:
        try:
            summary_docs.append(summary)
            stats["summary_count"] += 1

            if len(summary_docs) >= BATCH_SIZE:
                points = _create_points_batch(summary_docs)
                _upload_batch(CASELAW_SUMMARY_COLLECTION, points)
                summary_docs = []
                gc.collect()

        except Exception as e:
            logger.warning(f"Failed to process caselaw summary: {e}")
            stats["errors"] += 1

    # Upload remaining docs
    if summary_docs:
        points = _create_points_batch(summary_docs)
        _upload_batch(CASELAW_SUMMARY_COLLECTION, points)

    logger.info(f"Caselaw summary generation complete: {stats}")
    return stats


def _create_points_batch(docs: list) -> list[PointStruct]:
    """Create Qdrant PointStructs from documents with parallel batch embedding.

    Args:
        docs: List of documents with id, get_embedding_text(), and model_dump()

    Returns:
        List of PointStructs ready for upload
    """
    from lex.core.document import uri_to_uuid

    if not docs:
        return []

    texts = [doc.get_embedding_text() for doc in docs]
    embeddings = generate_hybrid_embeddings_batch(texts)

    return [
        PointStruct(
            id=uri_to_uuid(doc.id),
            vector={"dense": dense, "sparse": sparse},
            payload=doc.model_dump(mode="json"),
        )
        for doc, (dense, sparse) in zip(docs, embeddings)
    ]


def _upload_batch(
    collection: str,
    batch: list[PointStruct],
    chunk_size: int = 100,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> None:
    """Upload a batch of points to Qdrant in chunks with retry logic.

    Splits large batches into smaller chunks to avoid Qdrant's 32MB payload limit.
    Retries transient failures (e.g., read timeouts) with exponential backoff.

    Args:
        collection: Collection name
        batch: List of PointStructs to upload
        chunk_size: Maximum points per upload (default 100)
        max_retries: Maximum retry attempts per chunk
        retry_delay: Base delay between retries in seconds
    """
    if not batch:
        return

    import time

    # Upload in chunks to avoid payload size limits
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i : i + chunk_size]
        for attempt in range(max_retries):
            try:
                qdrant_client.upsert(
                    collection_name=collection,
                    points=chunk,
                    wait=True,
                )
                logger.debug(
                    f"Uploaded {len(chunk)} points to {collection} "
                    f"(chunk {i // chunk_size + 1}/{(len(batch) + chunk_size - 1) // chunk_size})"
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    logger.warning(
                        f"Upload to {collection} failed (attempt {attempt + 1}/{max_retries}): {e}, "
                        f"retrying in {delay}s"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Failed to upload chunk to {collection} after {max_retries} attempts: {e}"
                    )
                    raise


async def run_amendments_led_ingest(
    limit: int | None = None,
    enable_pdf_fallback: bool = False,
    years_back: int = 2,
    force: bool = False,
) -> dict:
    """Run amendment-led daily ingest.

    Uses amendments as a change manifest to identify which legislation
    needs refreshing, instead of blindly rescraping by year.

    Steps:
    1. Query amendments where affecting_year is within years_back
    2. Extract unique changed_legislation IDs
    3. Filter to stale or missing IDs (or all if force=True)
    4. Rescrape those specific legislation items
    5. Also ingest new amendments for those years

    Args:
        limit: Maximum number of items per source (None for unlimited)
        enable_pdf_fallback: Enable PDF processing for legislation without XML
        years_back: Number of years to look back (default: 2)
        force: Force rescrape of all amended legislation, skipping staleness check

    Returns:
        Statistics about the ingest run
    """
    current_year = date.today().year
    years = list(range(current_year - years_back + 1, current_year + 1))
    logger.info(
        f"Starting amendments-led ingest for years {years}, limit={limit}, force={force}"
    )

    stats = {}

    # Step 1-3: Get legislation IDs that were amended
    changed_ids = get_changed_legislation_ids(years)

    if force:
        rescrape_ids = set(changed_ids.keys())
        logger.info(f"Force mode: rescraping all {len(rescrape_ids)} amended legislation items")
    else:
        rescrape_ids = get_stale_or_missing_legislation_ids(changed_ids)

    stats["amendments_queried"] = {
        "changed_legislation_count": len(changed_ids),
        "rescrape_count": len(rescrape_ids),
        "force": force,
    }

    # Step 4: Rescrape stale/missing legislation by specific IDs
    if rescrape_ids:
        limited_ids = list(rescrape_ids)[:limit] if limit else list(rescrape_ids)
        stats["legislation_rescrape"] = await asyncio.to_thread(
            rescrape_legislation_by_ids, limited_ids, enable_pdf_fallback
        )
    else:
        stats["legislation_rescrape"] = {"count": 0, "skipped": "all up to date"}

    # Step 5: Also scrape new amendments
    # Note: caselaw ingest disabled - caselaw API has been taken down
    stage1_results = await asyncio.gather(
        asyncio.to_thread(ingest_amendments, years, limit),
        return_exceptions=True,
    )

    if isinstance(stage1_results[0], Exception):
        stats["amendments"] = {"error": str(stage1_results[0])}
    else:
        stats["amendments"] = stage1_results[0]

    logger.info(f"Amendments-led ingest complete: {stats}")
    return stats


def rescrape_legislation_by_ids(
    legislation_ids: list[str],
    enable_pdf_fallback: bool = False,
) -> dict:
    """Rescrape specific legislation items by their IDs.

    Args:
        legislation_ids: List of IDs like ["ukpga/2020/1", "uksi/2023/456"]
        enable_pdf_fallback: Enable PDF processing for items without XML

    Returns:
        Statistics about the rescrape
    """
    from lex.legislation.parser.xml_parser import LegislationParser as XMLLegislationParser
    from lex.legislation.pipeline import (
        _legislation_with_content_to_legislation,
        _provision_to_legislation_section,
    )
    from lex.legislation.scraper import LegislationScraper

    logger.info(f"Rescraping {len(legislation_ids)} legislation items by ID")

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
        "skipped": 0,
    }

    scraper = LegislationScraper()
    parser = XMLLegislationParser()
    legislation_docs: list = []
    section_docs: list = []

    for leg_id in legislation_ids:
        parsed = parse_legislation_id(leg_id)
        if not parsed:
            logger.warning(f"Invalid legislation ID format: {leg_id}")
            stats["skipped"] += 1
            continue

        leg_type, year, number = parsed
        url = f"https://www.legislation.gov.uk/{leg_type}/{year}/{number}/data.xml"

        try:
            # Scrape the legislation using the scraper's internal method
            soup = scraper._load_legislation_from_url(url)
            if soup is None:
                logger.warning(f"Failed to fetch {url}")
                stats["errors"] += 1
                continue

            # Parse full legislation with sections
            legislation_full = parser.parse(soup)
            if legislation_full is None:
                logger.warning(f"Failed to parse {url}")
                stats["errors"] += 1
                continue

            # Convert to Legislation model and collect doc
            legislation = _legislation_with_content_to_legislation(legislation_full)
            legislation_docs.append(legislation)
            stats["legislation_count"] += 1

            # Process sections
            for section in legislation_full.sections:
                leg_section = _provision_to_legislation_section(section, legislation_full.id)
                section_docs.append(leg_section)
                stats["section_count"] += 1

            # Process schedules
            for schedule in legislation_full.schedules:
                leg_section = _provision_to_legislation_section(schedule, legislation_full.id)
                section_docs.append(leg_section)
                stats["section_count"] += 1

            # Upload in batches
            if len(legislation_docs) >= BATCH_SIZE:
                points = _create_points_batch(legislation_docs)
                _upload_batch(LEGISLATION_COLLECTION, points)
                legislation_docs = []
                gc.collect()

            if len(section_docs) >= BATCH_SIZE:
                points = _create_points_batch(section_docs)
                _upload_batch(LEGISLATION_SECTION_COLLECTION, points)
                section_docs = []

        except Exception as e:
            logger.warning(f"Failed to rescrape {leg_id}: {e}")
            stats["errors"] += 1

    # Upload remaining docs
    if legislation_docs:
        points = _create_points_batch(legislation_docs)
        _upload_batch(LEGISLATION_COLLECTION, points)
    if section_docs:
        points = _create_points_batch(section_docs)
        _upload_batch(LEGISLATION_SECTION_COLLECTION, points)

    logger.info(f"Legislation ID-based rescrape complete: {stats}")
    return stats
