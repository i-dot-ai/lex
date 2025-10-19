import logging
import uuid
from typing import Iterator

from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.caselaw.parser import CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.pipeline_utils import PipelineMonitor, process_documents

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


def pipe_caselaw_unified(
    years: list[int], limit: int, types: list[Court], **kwargs
):
    """
    Unified pipeline that yields both Caselaw and CaselawSection documents.
    Note: This function doesn't use URL tracking or the simplified pipeline yet.
    It's kept for backwards compatibility with existing usage in main.py.
    """
    # For now, just import the parsers and run them separately
    from lex.caselaw.parser import CaselawAndCaselawSectionsParser

    scraper = CaselawScraper()
    parser = CaselawAndCaselawSectionsParser()
    run_id = str(uuid.uuid4())

    logger.info(f"Starting unified caselaw pipeline: run_id={run_id}")
    logger.warning("pipe_caselaw_unified doesn't use URL tracking yet - consider using separate pipelines")

    remaining_limit = limit if limit is not None else float("inf")

    for year in years:
        for court_type in types:
            content_iterator = scraper.load_content(
                years=[year], types=[court_type], limit=None
            )

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
