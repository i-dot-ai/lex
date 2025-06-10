import logging
from typing import Iterator

from lex.core.checkpoint import get_checkpoints
from lex.core.document import generate_documents
from lex.core.error_utils import ErrorCategorizer
from lex.core.pipeline_utils import PipelineMonitor
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

    checkpoints = get_checkpoints(years, types)

    for year, type in checkpoints:
        for url, soup in loader_or_scraper.load_content([year], limit, [type]):
            try:
                legislation = parser.parse_content(soup)
                yield from generate_documents([legislation], Legislation)
            except Exception as e:
                ErrorCategorizer.handle_error(logger, e)

@PipelineMonitor(doc_type="legislation_section", track_progress=True)
def pipe_legislation_sections(
    years: list[int], limit: int, types: list[LegislationType], **kwargs
) -> Iterator[LegislationSection]:
    scraper = LegislationScraper()
    parser = LegislationSectionParser()
    loader = LegislationLoader()

    if kwargs.get("from_file"):
        loader_or_scraper = loader
        logging.info("Loading legislation sections from file")
    else:
        loader_or_scraper = scraper
        logging.info("Parsing legislation sections from web")

    checkpoints = get_checkpoints(years, types)

    for year, type in checkpoints:
        for url, soup in loader_or_scraper.load_content([year], limit, [type]):
            try:
                legislation_sections = parser.parse_content(soup)
                yield from generate_documents(legislation_sections, LegislationSection)
            except Exception as e:
                ErrorCategorizer.handle_error(logger, e)
