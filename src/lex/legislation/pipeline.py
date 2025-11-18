import logging
import uuid
from typing import Iterator

from lex.core.pipeline_utils import PipelineMonitor, process_documents
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
