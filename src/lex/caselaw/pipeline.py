import logging
import uuid
from typing import Iterator

from qdrant_client.models import FieldCondition, Filter, MatchAny, Range

from lex.caselaw.models import Caselaw, CaselawSection, CaselawSummary, Court
from lex.caselaw.parser import CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.pipeline_utils import PipelineMonitor, process_documents
from lex.core.qdrant_client import qdrant_client
from lex.processing.caselaw_summaries.summary_generator import add_summaries_to_caselaw
from lex.settings import CASELAW_COLLECTION, CASELAW_SUMMARY_COLLECTION

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="caselaw", track_progress=True)
def pipe_caselaw(years: list[int], limit: int, types: list[Court], **kwargs) -> Iterator[Caselaw]:
    scraper = CaselawScraper()
    parser = CaselawParser()
    run_id = str(uuid.uuid4())

    logger.info(f"Starting caselaw pipeline: run_id={run_id}")

    yield from process_documents(
        years=years,
        types=types,
        loader_or_scraper=scraper,
        parser=parser,
        document_type=Caselaw,
        limit=limit,
        wrap_result=True,
        doc_type_name="caselaw",
        run_id=run_id,
        clear_tracking=kwargs.get("clear_checkpoint", False),
    )


@PipelineMonitor(doc_type="caselaw_section", track_progress=True)
def pipe_caselaw_sections(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[CaselawSection]:
    scraper = CaselawScraper()
    parser = CaselawSectionParser()
    run_id = str(uuid.uuid4())

    logger.info(f"Starting caselaw_section pipeline: run_id={run_id}")

    yield from process_documents(
        years=years,
        types=types,
        loader_or_scraper=scraper,
        parser=parser,
        document_type=CaselawSection,
        limit=limit,
        wrap_result=False,
        doc_type_name="caselaw_section",
        run_id=run_id,
        clear_tracking=kwargs.get("clear_checkpoint", False),
    )


def pipe_caselaw_unified(years: list[int], limit: int, types: list[Court], **kwargs):
    """
    Unified pipeline that yields both Caselaw and CaselawSection documents.

    Yields tuples of (collection_type, document):
        - ("caselaw", Caselaw) for core caselaw metadata
        - ("caselaw-section", CaselawSection) for each section

    Idempotency is handled by the caller using deterministic UUIDs.
    """
    from lex.caselaw.parser import CaselawAndCaselawSectionsParser

    scraper = CaselawScraper()
    parser = CaselawAndCaselawSectionsParser()
    run_id = str(uuid.uuid4())

    logger.info(f"Starting unified caselaw pipeline: run_id={run_id}")

    remaining_limit = limit if limit is not None else float("inf")

    for year in years:
        for court_type in types:
            content_iterator = scraper.load_content(years=[year], types=[court_type], limit=None)

            for url, soup in content_iterator:
                if remaining_limit <= 0:
                    return

                try:
                    result = parser.parse_content(soup)
                    if result:
                        caselaw, sections = result
                        remaining_limit -= 1

                        yield ("caselaw", caselaw)

                        for section in sections:
                            yield ("caselaw-section", section)

                except Exception as e:
                    logger.warning(f"Failed to parse {url}: {e}", exc_info=False)
                    continue


def _get_existing_summary_ids(caselaw_ids: list[str]) -> set[str]:
    """Check which caselaw items already have summaries in Qdrant."""
    if not caselaw_ids:
        return set()

    # Check if summary collection exists
    collections = qdrant_client.get_collections()
    collection_names = [c.name for c in collections.collections]
    if CASELAW_SUMMARY_COLLECTION not in collection_names:
        logger.info(f"Collection {CASELAW_SUMMARY_COLLECTION} doesn't exist yet")
        return set()

    # Query for existing summary IDs
    summary_ids = [f"{cid}-summary" for cid in caselaw_ids]
    existing = set()

    # Batch query in chunks of 100
    for i in range(0, len(summary_ids), 100):
        batch = summary_ids[i : i + 100]
        results, _ = qdrant_client.scroll(
            collection_name=CASELAW_SUMMARY_COLLECTION,
            scroll_filter=Filter(must=[FieldCondition(key="id", match=MatchAny(any=batch))]),
            limit=len(batch),
            with_payload=["id"],
            with_vectors=False,
        )
        for point in results:
            if point.payload and "id" in point.payload:
                # Extract original caselaw_id from summary ID
                summary_id = point.payload["id"]
                if summary_id.endswith("-summary"):
                    existing.add(summary_id[:-8])  # Remove "-summary" suffix

    return existing


@PipelineMonitor(doc_type="caselaw_summary", track_progress=True)
def pipe_caselaw_summaries(
    years: list[int],
    limit: int,
    types: list[Court],
    batch_size: int = 10,
    **kwargs,
) -> Iterator[CaselawSummary]:
    """
    Generate AI summaries for existing caselaw documents.

    Queries the caselaw collection for documents matching the criteria,
    filters out those that already have summaries, generates summaries
    for the rest, and yields CaselawSummary objects for upload.

    Args:
        years: Years to process
        limit: Maximum number of summaries to generate
        types: Court types to include
        batch_size: Number of cases to process in each batch (default: 10)
        **kwargs: Additional arguments (e.g., clear_checkpoint)

    Yields:
        CaselawSummary objects ready for upload to Qdrant
    """
    run_id = str(uuid.uuid4())
    logger.info(f"Starting caselaw_summary pipeline: run_id={run_id}")

    # Build filter conditions
    filter_conditions = []
    if types:
        filter_conditions.append(
            FieldCondition(key="court", match=MatchAny(any=[t.value for t in types]))
        )
    if years:
        min_year = min(years)
        max_year = max(years)
        filter_conditions.append(
            FieldCondition(key="year", range=Range(gte=min_year, lte=max_year))
        )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None

    # Scroll through caselaw collection in batches
    remaining = limit if limit else float("inf")
    offset = None
    total_processed = 0
    total_yielded = 0

    while remaining > 0:
        # Fetch a batch of caselaw documents
        fetch_size = min(batch_size, int(remaining)) if remaining != float("inf") else batch_size
        results, offset = qdrant_client.scroll(
            collection_name=CASELAW_COLLECTION,
            scroll_filter=query_filter,
            limit=fetch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            break

        # Convert to Caselaw objects
        caselaw_batch = []
        for point in results:
            try:
                caselaw = Caselaw(**point.payload)
                caselaw_batch.append(caselaw)
            except Exception as e:
                logger.warning(f"Failed to parse caselaw from Qdrant: {e}")
                continue

        # Filter out cases that already have summaries
        caselaw_ids = [c.id for c in caselaw_batch]
        existing_ids = _get_existing_summary_ids(caselaw_ids)
        cases_to_summarise = [c for c in caselaw_batch if c.id not in existing_ids]

        if existing_ids:
            logger.info(f"Skipping {len(existing_ids)} cases that already have summaries")

        if cases_to_summarise:
            # Generate summaries
            summaries = add_summaries_to_caselaw(cases_to_summarise)

            for summary in summaries:
                yield summary
                total_yielded += 1
                remaining -= 1

                if remaining <= 0:
                    break

        total_processed += len(caselaw_batch)
        logger.info(
            f"Progress: processed {total_processed} caselaw items, "
            f"yielded {total_yielded} summaries"
        )

        # Check if we've reached the end
        if offset is None:
            break

    logger.info(
        f"Completed caselaw_summary pipeline: {total_yielded} summaries generated "
        f"from {total_processed} caselaw items"
    )
