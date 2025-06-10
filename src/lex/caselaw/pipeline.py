import logging
from typing import Iterator

from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.caselaw.parser import CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.checkpoint import get_checkpoints
from lex.core.document import generate_documents
from lex.core.error_utils import ErrorCategorizer
from lex.core.pipeline_utils import PipelineMonitor

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="caselaw", track_progress=True)
def pipe_caselaw(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[Caselaw]:
    scraper = CaselawScraper()
    parser = CaselawParser()

    checkpoints = get_checkpoints(years, types)

    for year, court in checkpoints:
        for soup in scraper.load_content([year], limit, [court]):
            try:
                caselaw = parser.parse_content(soup)
                yield from generate_documents([caselaw], Caselaw)
            except Exception as e:
                ErrorCategorizer.handle_error(logger, e)


@PipelineMonitor(doc_type="caselaw_section", track_progress=True)
def pipe_caselaw_sections(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[CaselawSection]:
    scraper = CaselawScraper()
    parser = CaselawSectionParser()

    checkpoints = get_checkpoints(years, types)

    for year, court in checkpoints:
        for soup in scraper.load_content([year], limit, [court]):
            try:
                sections = parser.parse_content(soup)
                if sections:
                    yield from generate_documents(sections, CaselawSection)
            except Exception as e:
                ErrorCategorizer.handle_error(logger, e)
