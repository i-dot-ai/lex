import logging
from typing import Iterator

from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.caselaw.parser import CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.checkpoint import get_checkpoints
from lex.core.document import generate_documents
from lex.core.pipeline_utils import PipelineMonitor

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="caselaw", track_progress=True)
def pipe_caselaw(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[Caselaw]:
    scraper = CaselawScraper()
    parser = CaselawParser()

    checkpoints = get_checkpoints(years, types, "caselaw")

    for checkpoint in checkpoints:
        with checkpoint as ctx:
            for url, soup in scraper.load_content([checkpoint.year], limit, [checkpoint.doc_type]):
                result = ctx.process_item(url, lambda: parser.parse_content(soup))
                if result:
                    yield from generate_documents([result], Caselaw)


@PipelineMonitor(doc_type="caselaw_section", track_progress=True)
def pipe_caselaw_sections(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[CaselawSection]:
    scraper = CaselawScraper()
    parser = CaselawSectionParser()

    checkpoints = get_checkpoints(years, types, "caselaw_section")

    for checkpoint in checkpoints:
        with checkpoint as ctx:
            for url, soup in scraper.load_content([checkpoint.year], limit, [checkpoint.doc_type]):
                result = ctx.process_item(url, lambda: parser.parse_content(soup))
                if result:
                    yield from generate_documents(result, CaselawSection)
