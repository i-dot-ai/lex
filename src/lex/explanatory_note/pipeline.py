import logging
import uuid
from typing import Iterator

from lex.core.pipeline_utils import PipelineMonitor, process_documents
from lex.explanatory_note.models import ExplanatoryNote
from lex.explanatory_note.scraper import ExplanatoryNoteScraperAndParser
from lex.legislation.models import LegislationType

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="explanatory_note", track_progress=True)
def pipe_explanatory_note(
    years: list[int], types: list[LegislationType], limit: int = None, **kwargs
) -> Iterator[ExplanatoryNote]:
    """
    Note: Explanatory notes use a combined scraper-parser, so this is kept simple.
    URL tracking not yet implemented for this pipeline - uses old pattern.
    """
    scraper_parser = ExplanatoryNoteScraperAndParser()
    run_id = str(uuid.uuid4())

    logger.info(f"Starting explanatory_note pipeline: run_id={run_id}")
    logger.warning("pipe_explanatory_note doesn't use URL tracking yet")

    remaining_limit = limit if limit is not None else float("inf")

    for year in years:
        for doc_type in types:
            for url, content in scraper_parser.scrape_and_parse_content([year], [doc_type]):
                if remaining_limit <= 0:
                    return

                try:
                    if content:
                        remaining_limit -= 1
                        yield ExplanatoryNote(**content)
                except Exception as e:
                    logger.warning(f"Failed to process {url}: {e}", exc_info=False)
                    continue
