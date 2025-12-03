import logging
import uuid
from typing import Iterator

from lex.core.pipeline_utils import PipelineMonitor, process_documents
from lex.legislation.loader import LegislationLoader
from lex.legislation.models import (
    Legislation,
    LegislationSection,
    LegislationType,
    LegislationWithContent,
    Schedule,
    Section,
)
from lex.legislation.parser import LegislationParser, LegislationSectionParser
from lex.legislation.parser.xml_parser import LegislationParser as XMLLegislationParser
from lex.legislation.scraper import LegislationScraper

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="legislation", track_progress=True)
def pipe_legislation(
    years: list[int], limit: int, types: list[LegislationType], **kwargs
) -> Iterator[Legislation]:
    scraper = LegislationScraper()
    parser = LegislationParser()
    loader = LegislationLoader()
    run_id = str(uuid.uuid4())

    if kwargs.get("from_file"):
        loader_or_scraper = loader
        logger.info(f"Loading legislation from file: run_id={run_id}")
    else:
        loader_or_scraper = scraper
        logger.info(f"Parsing legislation from web: run_id={run_id}")

    yield from process_documents(
        years=years,
        types=types,
        loader_or_scraper=loader_or_scraper,
        parser=parser,
        document_type=Legislation,
        limit=limit,
        wrap_result=True,
        doc_type_name="legislation",
        run_id=run_id,
        clear_tracking=kwargs.get("clear_checkpoint", False),
    )


@PipelineMonitor(doc_type="legislation_section", track_progress=True)
def pipe_legislation_sections(
    years: list[int], limit: int, types: list[LegislationType], **kwargs
) -> Iterator[LegislationSection]:
    scraper = LegislationScraper()
    loader = LegislationLoader()
    parser = LegislationSectionParser()
    run_id = str(uuid.uuid4())

    if kwargs.get("from_file"):
        loader_or_scraper = loader
        logger.info(f"Loading legislation sections from file: run_id={run_id}")
    else:
        loader_or_scraper = scraper
        logger.info(f"Parsing legislation sections from web: run_id={run_id}")

    yield from process_documents(
        years=years,
        types=types,
        loader_or_scraper=loader_or_scraper,
        parser=parser,
        document_type=LegislationSection,
        limit=limit,
        wrap_result=False,
        doc_type_name="legislation_section",
        run_id=run_id,
        clear_tracking=kwargs.get("clear_checkpoint", False),
    )


def _provision_to_legislation_section(
    provision: Section | Schedule,
    legislation_id: str,
) -> LegislationSection:
    """Convert a Section or Schedule to a LegislationSection for Qdrant storage."""
    return LegislationSection(
        id=provision.id,
        uri=provision.uri,
        legislation_id=legislation_id,
        title=provision.title,
        text=provision.text,
        extent=provision.extent,
        provision_type=provision.provision_type,
    )


def _legislation_with_content_to_legislation(
    leg_with_content: LegislationWithContent,
) -> Legislation:
    """Convert LegislationWithContent to Legislation (strips sections/schedules)."""
    return Legislation(
        id=leg_with_content.id,
        uri=leg_with_content.uri,
        title=leg_with_content.title,
        description=leg_with_content.description,
        enactment_date=leg_with_content.enactment_date,
        valid_date=leg_with_content.valid_date,
        modified_date=leg_with_content.modified_date,
        publisher=leg_with_content.publisher,
        category=leg_with_content.category,
        type=leg_with_content.type,
        year=leg_with_content.year,
        number=leg_with_content.number,
        status=leg_with_content.status,
        extent=leg_with_content.extent,
        number_of_provisions=leg_with_content.number_of_provisions,
        text=leg_with_content.text if hasattr(leg_with_content, "text") else "",
        provenance_source=leg_with_content.provenance_source,
        provenance_model=leg_with_content.provenance_model,
        provenance_prompt_version=leg_with_content.provenance_prompt_version,
        provenance_timestamp=leg_with_content.provenance_timestamp,
        provenance_response_id=leg_with_content.provenance_response_id,
    )


def pipe_legislation_unified(
    years: list[int],
    limit: int,
    types: list[LegislationType],
    enable_pdf_fallback: bool = False,
    **kwargs,
):
    """
    Unified pipeline that yields both Legislation and LegislationSection documents.

    This function scrapes legislation from legislation.gov.uk, parses the full
    content including sections and schedules, and yields them as separate
    documents for storage in their respective Qdrant collections.

    When PDF fallback is enabled, legislation items with empty/missing XML content
    will be processed using the PDF processor (LLM-based OCR), which is more
    expensive but ensures complete data coverage.

    Args:
        years: List of years to scrape
        limit: Maximum number of legislation items to process (None for unlimited)
        types: List of LegislationType values to include
        enable_pdf_fallback: If True, attempt PDF processing when XML fails/empty
        **kwargs: Additional arguments (e.g., clear_checkpoint)

    Yields:
        Tuples of (collection_type, document) where:
        - ("legislation", Legislation) for core legislation metadata
        - ("legislation-section", LegislationSection) for each section/schedule
    """
    scraper = LegislationScraper()
    parser = XMLLegislationParser()
    run_id = str(uuid.uuid4())

    logger.info(
        f"Starting unified legislation pipeline: run_id={run_id}, "
        f"pdf_fallback={enable_pdf_fallback}"
    )

    remaining_limit = limit if limit is not None else float("inf")
    pdf_fallback_count = 0

    for year in years:
        for leg_type in types:
            # Filter types by year to avoid scraping non-existent combinations
            valid_types = LegislationType.filter_by_year([leg_type], year)
            if not valid_types:
                continue

            content_iterator = scraper.load_content(
                years=[year], types=[leg_type], limit=None
            )

            for url, soup in content_iterator:
                if remaining_limit <= 0:
                    logger.info(f"Reached limit of {limit} items")
                    if pdf_fallback_count > 0:
                        logger.info(f"PDF fallback used for {pdf_fallback_count} items")
                    return

                xml_succeeded = False
                try:
                    # Parse full legislation with sections and schedules
                    legislation_full = parser.parse(soup)

                    if legislation_full is None:
                        logger.debug(f"XML parse returned None for {url}")
                    elif not _is_content_valid(legislation_full):
                        logger.debug(f"XML content too short for {url}")
                    else:
                        xml_succeeded = True
                        remaining_limit -= 1

                        # Yield the core legislation (without sections for embedding)
                        legislation = _legislation_with_content_to_legislation(
                            legislation_full
                        )
                        yield ("legislation", legislation)

                        # Yield each section as a LegislationSection
                        for section in legislation_full.sections:
                            leg_section = _provision_to_legislation_section(
                                section, legislation_full.id
                            )
                            yield ("legislation-section", leg_section)

                        # Yield each schedule as a LegislationSection
                        for schedule in legislation_full.schedules:
                            leg_section = _provision_to_legislation_section(
                                schedule, legislation_full.id
                            )
                            yield ("legislation-section", leg_section)

                except Exception as e:
                    logger.debug(f"XML parse failed for {url}: {e}")

                # PDF fallback if XML failed/empty and fallback is enabled
                if not xml_succeeded and enable_pdf_fallback:
                    pdf_result = _try_pdf_fallback(url)
                    if pdf_result:
                        legislation, sections = pdf_result
                        remaining_limit -= 1
                        pdf_fallback_count += 1

                        yield ("legislation", legislation)
                        for section in sections:
                            yield ("legislation-section", section)
                    else:
                        logger.warning(f"Both XML and PDF failed for {url}")

    if pdf_fallback_count > 0:
        logger.info(f"PDF fallback used for {pdf_fallback_count} items")


def _is_content_valid(legislation_full: LegislationWithContent) -> bool:
    """Check if the legislation content is valid (not empty/too short)."""
    min_length = 100
    text = legislation_full.text if hasattr(legislation_full, "text") else ""
    return len(text.strip()) >= min_length


def _try_pdf_fallback(url: str) -> tuple[Legislation, list[LegislationSection]] | None:
    """
    Attempt PDF fallback for a legislation URL.

    Args:
        url: XML URL like https://www.legislation.gov.uk/uksi/2025/123/data.xml

    Returns:
        Tuple of (Legislation, sections) or None if failed
    """
    import re

    from lex.legislation.pdf_fallback import process_pdf_legislation_sync

    # Extract legislation ID from URL
    match = re.search(r"legislation\.gov\.uk/([^/]+/[^/]+/[^/]+)", url)
    if not match:
        logger.warning(f"Could not extract legislation ID from {url}")
        return None

    legislation_id = match.group(1)

    try:
        result = process_pdf_legislation_sync(legislation_id)
        if result:
            logger.info(f"PDF fallback succeeded for {legislation_id}")
        return result
    except Exception as e:
        logger.warning(f"PDF fallback failed for {legislation_id}: {e}")
        return None
