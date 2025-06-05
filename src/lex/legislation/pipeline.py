import logging
from typing import Iterator

from lex.core.document import generate_documents
from lex.core.exceptions import LexParsingError
from lex.legislation.loader import LegislationLoader
from lex.legislation.models import Legislation, LegislationSection, LegislationType
from lex.legislation.parser import LegislationParser, LegislationSectionParser
from lex.legislation.scraper import LegislationScraper

logger = logging.getLogger(__name__)


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

    for soup in loader_or_scraper.load_content(years, limit, types):
        try:
            legislation = parser.parse_content(soup)
            yield from generate_documents([legislation], Legislation)
        except LexParsingError as e:
            logger.error(e)
        except Exception as e:
            logger.error(f"Error parsing legislation: {e}", exc_info=True)


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

    for soup in loader_or_scraper.load_content(years, limit, types):
        try:
            legislation_sections = parser.parse_content(soup)
            yield from generate_documents(legislation_sections, LegislationSection)
        except LexParsingError as e:
            logger.error(e)
        except Exception as e:
            logger.error(f"Error parsing legislation sections: {e}", exc_info=True)
