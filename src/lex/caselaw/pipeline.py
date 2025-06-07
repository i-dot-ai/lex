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
            # Try to extract metadata from error or soup
            error_msg = str(e)
            doc_id = None
            court = None
            year = None
            
            # Try to extract from soup if available
            try:
                if soup and hasattr(soup, 'find'):
                    # Try to get ID from metadata
                    id_elem = soup.find('uk:cite')
                    if id_elem:
                        doc_id = id_elem.get_text()
            except:
                pass
            
            logger.error(
                f"Error parsing caselaw: {error_msg}",
                extra={
                    "doc_id": doc_id,
                    "doc_type": "caselaw",
                    "processing_status": "parse_error",
                    "error_type": "LexParsingError",
                    "court": court,
                    "doc_year": year
                }
            )
        except Exception as e:
            logger.error(
                f"Error parsing caselaw: {e}",
                exc_info=True,
                extra={
                    "doc_type": "caselaw",
                    "processing_status": "error",
                    "error_type": type(e).__name__
                }
            )


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
            # Try to extract metadata from error or soup
            error_msg = str(e)
            doc_id = None
            
            # Try to extract from soup if available
            try:
                if soup and hasattr(soup, 'find'):
                    # Try to get ID from metadata
                    id_elem = soup.find('uk:cite')
                    if id_elem:
                        doc_id = id_elem.get_text()
            except:
                pass
            
            logger.error(
                f"Error parsing caselaw sections: {error_msg}",
                extra={
                    "doc_id": doc_id,
                    "doc_type": "caselaw",
                    "processing_status": "parse_error",
                    "error_type": "LexParsingError"
                }
            )
        except Exception as e:
            logger.error(
                f"Error parsing caselaw sections: {e}",
                exc_info=True,
                extra={
                    "doc_type": "caselaw",
                    "processing_status": "error",
                    "error_type": type(e).__name__
                }
            )
