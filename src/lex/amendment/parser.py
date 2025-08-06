import logging

from bs4 import BeautifulSoup

from lex.core.parser import LexParser

from .models import Amendment

logger = logging.getLogger(__name__)

class AmendmentParser(LexParser):
    """
    Parser for amendments to legislation. Takes a BeautifulSoup object and returns a list of Amendment objects.
    """

    def __init__(
        self,
        base_url: str = "http://www.legislation.gov.uk",
    ):
        self.base_url = base_url

    def parse_content(self, soup: BeautifulSoup) -> list[Amendment]:
        table = soup.find("table")
        if not table:
            return []

        rows = table.find("tbody").find_all("tr")

        rows = [self._row_to_amendment(row) for row in rows]

        amendments = [row for row in rows if row is not None]

        if amendments:
            # Log successful parsing with structured data
            logger.info(
                f"Parsed {len(amendments)} amendments",
                extra={
                    "doc_type": "amendment",
                    "processing_status": "success",
                    "amendment_count": len(amendments),
                    # Sample first amendment for context
                    "sample_changed": amendments[0].changed_legislation if amendments else None,
                    "sample_affecting": amendments[0].affecting_legislation if amendments else None,
                },
            )

        return amendments

    def _row_to_amendment(self, row: BeautifulSoup) -> Amendment:
        """Convert a table row to an Amendment object."""
        cols = row.find_all("td")

        changed_year, changed_number = self._get_year_number(cols[1].text)
        affecting_year, affecting_number = self._get_year_number(cols[5].text)
        changed_url = self._get_href_if_exists(cols[1])
        affecting_url = self._get_href_if_exists(cols[5])

        return Amendment(
            changed_legislation=cols[0].text,
            changed_year=changed_year,
            changed_number=changed_number,
            changed_url=changed_url,
            changed_provision=cols[2].text,
            changed_provision_url=self._get_href_if_exists(cols[2]),
            affecting_legislation=cols[4].text,
            affecting_year=affecting_year,
            affecting_number=affecting_number,
            affecting_url=affecting_url,
            affecting_provision=cols[6].text,
            affecting_provision_url=self._get_href_if_exists(cols[6]),
            type_of_effect=cols[3].text,
            id=f"changed-{changed_url}-affecting-{affecting_url}",
        )

    def _get_href_if_exists(self, soup: BeautifulSoup) -> str | None:
        """Get href from soup if it exists."""
        x = soup.find("a")
        if x:
            try:
                return self.base_url + x["href"]
            except KeyError:
                return None
        return None

    def _get_year_number(self, text: str) -> tuple[str | None, str | None]:
        try:
            return text.split("\xa0")[0], text.split("\xa0")[1]
        except IndexError:
            return None, None
