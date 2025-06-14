import logging
from typing import Iterator

from lex.core.checkpoint import get_checkpoints
from lex.core.pipeline_utils import (
    PipelineMonitor,
    process_checkpoints_with_combined_scraper_parser,
)
from lex.explanatory_note.models import ExplanatoryNote
from lex.explanatory_note.scraper import ExplanatoryNoteScraperAndParser
from lex.legislation.models import LegislationType

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="explanatory_note", track_progress=True)
def pipe_explanatory_note(
    years: list[int], types: list[LegislationType], limit: int = None, **kwargs
) -> Iterator[ExplanatoryNote]:
    scraper_and_parser = ExplanatoryNoteScraperAndParser()

    checkpoints = get_checkpoints(
        years, types, "explanatory_note", kwargs.get("clear_checkpoint", False)
    )

    yield from process_checkpoints_with_combined_scraper_parser(
        checkpoints=checkpoints,
        scraper_parser=scraper_and_parser,
        document_type=ExplanatoryNote,
        limit=limit,
        wrap_result=True,
    )
