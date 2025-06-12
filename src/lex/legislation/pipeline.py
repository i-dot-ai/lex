import logging
from typing import Iterator

from lex.core.checkpoint import get_checkpoints
from lex.core.pipeline_utils import PipelineMonitor, process_checkpoints
from lex.legislation.loader import LegislationLoader
from lex.legislation.models import Legislation, LegislationSection, LegislationType
from lex.legislation.parser import LegislationParser, LegislationSectionParser
from lex.legislation.scraper import LegislationScraper

logger = logging.getLogger(__name__)

@PipelineMonitor(doc_type="legislation", track_progress=True)
def pipe_legislation(
    years: list[int], limit: int, types: list[LegislationType], **kwargs
) -> Iterator[Legislation]:
    scraper = LegislationScraper()
    parser = LegislationParser()
    loader = LegislationLoader()

    if kwargs.get("from_file"):
        loader_or_scraper = loader
        logging.info("Loading legislation from file")
    else:
        loader_or_scraper = scraper
        logging.info("Parsing legislation from web")

    checkpoints = get_checkpoints(years, types, "legislation")

    yield from process_checkpoints(
        checkpoints=checkpoints,
        loader_or_scraper=loader_or_scraper,
        parser=parser,
        document_type=Legislation,
        limit=limit,
        wrap_result=True
    )

@PipelineMonitor(doc_type="legislation_section", track_progress=True)
def pipe_legislation_sections(
    years: list[int], limit: int, types: list[LegislationType], **kwargs
) -> Iterator[LegislationSection]:
    scraper = LegislationScraper()
    loader = LegislationLoader()
    parser = LegislationSectionParser()

    if kwargs.get("from_file"):
        loader_or_scraper = loader
        logging.info("Loading legislation sections from file")
    else:
        loader_or_scraper = scraper
        logging.info("Parsing legislation sections from web")

    checkpoints = get_checkpoints(years, types, "legislation_section")

    yield from process_checkpoints(
        checkpoints=checkpoints,
        loader_or_scraper=loader_or_scraper,
        parser=parser,
        document_type=LegislationSection,
        limit=limit,
        wrap_result=False
    )


