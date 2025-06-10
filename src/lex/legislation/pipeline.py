import logging
from typing import Iterator

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

    # Pass checkpoint parameters if loading from web
    if loader_or_scraper == scraper:
        content_iterator = loader_or_scraper.load_content(
            years,
            limit,
            types,
            use_checkpoint=not kwargs.get("no_checkpoint", False),
            clear_checkpoint=kwargs.get("clear_checkpoint", False),
            checkpoint_suffix="_documents",  # Different suffix for document pipeline
        )
    else:
        content_iterator = loader_or_scraper.load_content(years, limit, types)

    for url, soup in content_iterator:
        try:
            # Parse the legislation - simple business logic
            legislation = parser.parse_content(soup)
            yield from generate_documents([legislation], Legislation)
        except Exception as e:
            # Use error categorizer for consistent handling
            if ErrorCategorizer.is_recoverable_error(e):
                logger.error(
                    ErrorCategorizer.get_error_summary(e),
                    extra=ErrorCategorizer.extract_error_metadata(e)
                )
                # Continue processing next document
            else:
                # Non-recoverable error
                raise


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

    # Pass checkpoint parameters if loading from web
    if loader_or_scraper == scraper:
        content_iterator = loader_or_scraper.load_content(
            years,
            limit,
            types,
            use_checkpoint=not kwargs.get("no_checkpoint", False),
            clear_checkpoint=kwargs.get("clear_checkpoint", False),
            checkpoint_suffix="_sections",  # Different suffix for sections pipeline
        )
    else:
        content_iterator = loader_or_scraper.load_content(years, limit, types)

    for url, soup in content_iterator:
        try:
            # Parse sections
            legislation_sections = parser.parse_content(soup)

            if legislation_sections:
                yield from generate_documents(legislation_sections, LegislationSection)
        except Exception as e:
            # Use error categorizer for consistent handling
            if ErrorCategorizer.is_recoverable_error(e):
                logger.error(
                    ErrorCategorizer.get_error_summary(e),
                    extra=ErrorCategorizer.extract_error_metadata(e)
                )
                # Continue processing next document
            else:
                # Non-recoverable error
                raise
