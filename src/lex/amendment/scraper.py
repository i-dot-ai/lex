import logging
from typing import Iterator, Optional, Tuple

from bs4 import BeautifulSoup

from lex.core.http import HttpClient

from .models import Amendment

http_client = HttpClient()

logger = logging.getLogger(__name__)


class AmendmentScraper:
    """Scraper for legislation amendments."""

    def __init__(
        self,
        base_url: str = "https://www.legislation.gov.uk",
    ):
        self.base_url = base_url

    def load_content(
        self,
        years: list[int],
        limit: int = 200,
        types: list = None,  # Not used for amendments, but required for pipeline compatibility
        year_made_by: Optional[int] = None,
        page: int = 1,
        results_count: int = 100,
    ) -> Iterator[tuple[str, Amendment]]:
        """
        Get legislation changes as a generator of Amendment objects.

        Args:
            years: The years of the affected legislation
            limit: Maximum number of results to return
            year_made_by: Optional year of the affecting legislation that the amendments came from
            page: Starting page number
            results_count: Number of results per page

        Yields:
            Amendment objects
        """
        # Sort years in descending order
        years = sorted(years, reverse=True)

        count = 0
        for year_affected in years:
            page = 1

            while True:
                # Check if we've reached the limit, if so, break. Otherwise, fetch the next page.
                if count >= limit:
                    break

                url = self._get_url_legislation_changes(
                    year_affected, year_made_by, page=page, results_count=results_count
                )

                logger.debug(f"Fetching page {page}: {url}")

                res = http_client.get(url)
                soup = BeautifulSoup(res.content, "html.parser")

                # If the page has no results, we've reached the end of the amendments for this year and can break which will move us onto the next year.
                if not self._page_has_results(soup):
                    break

                yield url, soup
                count += results_count
                page += 1

            if count >= limit:
                break

    def _get_year_number(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract year and number from text."""
        try:
            return text.split("\xa0")[0], text.split("\xa0")[1]
        except IndexError:
            return None, None

    def _get_url_legislation_changes(
        self,
        year_affected: int,
        year_made_by: Optional[int] = None,
        results_count: int = 100,
        page: int = 1,
    ) -> str:
        """Generate URL for legislation changes."""
        url = f"{self.base_url}/changes/affected/all/{year_affected}"
        url = url + f"/affecting/all/{year_made_by}" if year_made_by else url
        url = url + f"?results-count={results_count}&page={page}&sort=affected-year-number"
        return url

    def _page_has_results(self, soup: BeautifulSoup) -> bool:
        table = soup.find("table")
        if table:
            return True
        return False
