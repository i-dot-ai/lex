import logging
from typing import Iterator

from bs4 import BeautifulSoup

from lex.caselaw.models import Court
from lex.core.http import HttpClient
from lex.core.scraper import LexScraper

logger = logging.getLogger(__name__)
# Create a more resilient HTTP client for caselaw scraping
from lex.core.rate_limiter import AdaptiveRateLimiter

# Create custom rate limiter with longer backoffs
rate_limiter = AdaptiveRateLimiter(
    min_delay=0.0,
    max_delay=300.0,  # Max 5 minutes between requests
    success_reduction_factor=0.98,  # Slower reduction
    failure_increase_factor=3.0,  # More aggressive backoff
)

http_client = HttpClient(
    max_retries=20,  # Increased from default 5
    initial_delay=2.0,  # Start with 2 seconds
    max_delay=600.0,  # Max 10 minutes between retries
    timeout=30,  # Increased timeout
    enable_cache=True,
    cache_size_limit=1000000,
    cache_ttl=3600,
)
# Replace the default rate limiter with our custom one
http_client.rate_limiter = rate_limiter


class CaselawScraper(LexScraper):
    """Scraper for caselaw content from the National Archives."""

    def __init__(self):
        self.BASE_URL = "https://caselaw.nationalarchives.gov.uk"

    def load_content(
        self,
        years: list[int] | None = None,
        limit: int = 50,
        types: list[Court] | None = None,
        results_per_page: int = 50,
    ) -> Iterator[tuple[str, BeautifulSoup]]:
        """Scrapes National Archives content, returning tuples of (BeautifulSoup, case_url)."""

        case_urls = self._get_cases_urls(
            page_offset=0, results_per_page=results_per_page, limit=limit, years=years, types=types
        )

        for case_url in case_urls:
            try:
                logger.debug(f"Requesting case from {case_url}")
                xml_url = case_url + "/data.xml"
                res = http_client.get(xml_url)

                # Use lxml parser which is more memory efficient
                soup = BeautifulSoup(res.text, "xml")

                # Yield both soup and the original case URL
                yield case_url, soup

            except Exception as e:
                logger.error(f"Error with case {case_url}: {str(e)}", exc_info=True)

    def _get_request_url(
        self,
        page_offset: int = 0,
        results_per_page: int = 50,
        years: list[int] | None = None,
        types: list[Court] | None = None,
    ) -> str:
        """
        Constructs the request URL with appropriate filters.
        If years is provided, validates that the years are consecutive and adds date filtering.
        If types is provided, adds court type filtering.

        Args:
            page_offset: The page offset for pagination
            results_per_page: Number of results per page
            years: Optional list of years to filter by
            types: Optional list of Court enums to filter by

        Returns:
            The constructed request URL

        Raises:
            ValueError: If the years list contains non-consecutive years
        """
        base_query = f"{self.BASE_URL}/judgments/search?query=&order=-date&page={page_offset + 1}&per_page={results_per_page}"

        # Add year filtering if specified
        if years:
            # Validate that years are consecutive
            if len(years) > 1:
                years_sorted = sorted(years)
                for i in range(1, len(years_sorted)):
                    if years_sorted[i] != years_sorted[i - 1] + 1:
                        raise ValueError(
                            f"Years must be consecutive. Found gap between {years_sorted[i - 1]} and {years_sorted[i]}"
                        )

            min_year = min(years)
            max_year = max(years)

            # Add year filtering to the URL
            base_query += f"&from_date_2={min_year}&to_date_2={max_year}"

        # Add court type filtering if specified
        if types:
            for court in types:
                base_query += f"&court={court.value}"

        return base_query

    def _get_cases_urls(
        self,
        page_offset: int = 0,
        results_per_page: int = 50,
        limit: int = 50,
        years: list[int] | None = None,
        types: list[Court] | None = None,
    ) -> Iterator[str]:
        request_url = self._get_request_url(
            page_offset=page_offset, results_per_page=results_per_page, years=years, types=types
        )

        print(request_url)
        logger.info(f"Requesting {limit} cases from {request_url}")

        page_counter = 0
        return_counter = 0
        while return_counter < limit:
            logger.debug(f"Requesting page {page_counter + 1} from {request_url}")
            try:
                res = http_client.get(request_url)
                soup = BeautifulSoup(res.text, "html.parser")
                cases = self._get_cases_from_contents_soup(soup)
                for case in cases:
                    return_counter += 1
                    if return_counter > limit:
                        break
                    yield case
                page_counter += 1
                request_url = self._get_next_page_url(soup)
                if not request_url:
                    break
            except Exception as e:
                logger.error(f"Error fetching page {page_counter + 1}: {str(e)}")
                break

    def _get_cases_from_contents_soup(self, soup: BeautifulSoup) -> Iterator[str]:
        list_elements =soup.find("div", class_="judgments-table").find("table").find_all("tr")
        links = [element.find("a")["href"] for element in list_elements[1:]]
        links = [self.BASE_URL + element.split("?")[0] for element in links]
        return links

    def _get_next_page_url(self, soup: BeautifulSoup) -> str | None:
        next_page = soup.find("a", class_="pagination__page-chevron-next")
        if next_page:
            return self.BASE_URL + next_page["href"]
        else:
            return None
