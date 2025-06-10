import logging
from typing import Iterator

from lex.core.checkpoint import get_checkpoints
from lex.core.document import generate_documents
from lex.core.error_utils import ErrorCategorizer
from lex.core.pipeline_utils import PipelineMonitor
from lex.explanatory_note.models import ExplanatoryNote
from lex.explanatory_note.scraper import ExplanatoryNoteScraperAndParser
from lex.legislation.models import LegislationType

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="explanatory_note", track_progress=True)
def pipe_explanatory_note(
    years: list[int], types: list[LegislationType], limit: int = None, **kwargs
) -> Iterator[ExplanatoryNote]:
    scraper_and_parser = ExplanatoryNoteScraperAndParser()

    checkpoints = get_checkpoints(years, types)

    for year, leg_type in checkpoints:
        for url, note in scraper_and_parser.scrape_and_parse_content([year], [leg_type], limit):
            try:
                yield from generate_documents([note], ExplanatoryNote)
            except Exception as e:
                ErrorCategorizer.handle_error(logger, e)
