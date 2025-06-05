import logging
from typing import Iterator

from lex.core.document import generate_documents

from .models import Amendment
from .parser import AmendmentParser
from .scraper import AmendmentScraper

logger = logging.getLogger(__name__)


def pipe_amendments(years: list[int], limit: int, **kwargs) -> Iterator[Amendment]:
    """Generate amendments documents for Elasticsearch."""
    scraper = AmendmentScraper()
    parser = AmendmentParser()

    for soup in scraper.load_content(years, limit):
        try:
            amendments = parser.parse_content(soup)
            logger.info(f"Parsed amendments: {len(amendments)}")
            yield from generate_documents(amendments, Amendment)
        except Exception as e:
            logger.error(f"Error parsing amendments: {e}", exc_info=True)
