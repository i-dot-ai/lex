import logging
from typing import Iterable

from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.caselaw.parser import CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.document import generate_documents
from lex.core.exceptions import LexParsingError

logger = logging.getLogger(__name__)


def pipe_caselaw(
    years: list[int], limit: int, types: list[Court] | None = None, **kwargs
) -> Iterable[Caselaw]:
    scraper = CaselawScraper()
    parser = CaselawParser()

    for soup in scraper.load_content(years, limit, types=types):
        try:
            caselaw = parser.parse_content(soup)
            yield from generate_documents([caselaw], Caselaw)
        except LexParsingError as e:
            logger.error(f"Error parsing caselaw: {e}")
        except Exception as e:
            logger.error(f"Error parsing caselaw: {e}", exc_info=True)


def pipe_caselaw_sections(
    years: list[int], limit: int, types: list[Court] | None = None, **kwargs
) -> Iterable[CaselawSection]:
    scraper = CaselawScraper()
    parser = CaselawSectionParser()

    for soup in scraper.load_content(years, limit, types=types):
        try:
            caselaw_sections = parser.parse_content(soup)
            yield from generate_documents(caselaw_sections, CaselawSection)
        except LexParsingError as e:
            logger.error(f"Error parsing caselaw sections: {e}")
        except Exception as e:
            logger.error(f"Error parsing caselaw sections: {e}", exc_info=True)
