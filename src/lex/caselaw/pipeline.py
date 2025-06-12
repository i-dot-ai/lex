import logging
from typing import Iterator

from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.caselaw.parser import CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.checkpoint import get_checkpoints
from lex.core.pipeline_utils import PipelineMonitor, process_checkpoints

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="caselaw", track_progress=True)
def pipe_caselaw(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[Caselaw]:
    scraper = CaselawScraper()
    parser = CaselawParser()

    checkpoints = get_checkpoints(years, types, "caselaw")

    yield from process_checkpoints(
        checkpoints=checkpoints,
        loader_or_scraper=scraper,
        parser=parser,
        document_type=Caselaw,
        limit=limit,
        wrap_result=True
    )


@PipelineMonitor(doc_type="caselaw_section", track_progress=True)
def pipe_caselaw_sections(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[CaselawSection]:
    scraper = CaselawScraper()
    parser = CaselawSectionParser()

    checkpoints = get_checkpoints(years, types, "caselaw_section")

    yield from process_checkpoints(
        checkpoints=checkpoints,
        loader_or_scraper=scraper,
        parser=parser,
        document_type=CaselawSection,
        limit=limit,
        wrap_result=False
    )
