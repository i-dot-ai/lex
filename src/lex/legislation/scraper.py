import logging
from typing import Iterator

from bs4 import BeautifulSoup

from lex.core.http import HttpClient
from lex.legislation.models import LegislationType

http_client = HttpClient()

logger = logging.getLogger(__name__)

# Acts of Parliament Numbering and Citation Act 1962 established calendar year numbering
# Before 1963, legislation used regnal year numbering
HISTORICAL_CUTOFF_YEAR = 1963


class LegislationScraper:
    def __init__(self):
        self.base_url = "https://www.legislation.gov.uk"
        # Cache Atom feed results at year level to avoid redundant requests
        # Key: year, Value: list of all URLs discovered for that year
        self._historical_year_cache = {}

    def load_content(
        self,
        years: list[int],
        limit: int | None = None,
        types: list[LegislationType] = list(LegislationType),
    ) -> Iterator[tuple[str, BeautifulSoup]]:
        "Scrapes legislation content from the internet."

        legislation_urls = self.load_urls(years, types, limit)

        for url in legislation_urls:
            soup = self._load_legislation_from_url(url)
            yield url, soup

    def load_urls(
        self,
        years: list[int],
        types: list[LegislationType],
        limit: int | None = None,
        include_xml=True,
    ) -> Iterator[str]:
        """
        Load legislation URLs for given years and types.

        Automatically uses appropriate discovery method:
        - Modern (1963+): HTML page scraping by type/year
        - Historical (pre-1963): Atom feed discovery

        Per Acts of Parliament Numbering and Citation Act 1962:
        "Acts passed in 1963 and every subsequent year shall be assigned
        by reference to the calendar year" - hence 1963 is the cutoff.
        """
        count = 0

        # Separate years into modern and historical
        modern_years = [y for y in years if y >= HISTORICAL_CUTOFF_YEAR]
        historical_years = [y for y in years if y < HISTORICAL_CUTOFF_YEAR]

        # Process modern years (type/year page scraping)
        for year in modern_years:
            for type in types:
                urls = self._get_legislation_urls_from_type_year(type.value, year, include_xml)
                for url in urls:
                    yield url
                    count += 1
                    if limit and count >= limit:
                        return

        # Process historical years (Atom feed discovery)
        for year in historical_years:
            urls = self._get_historical_urls_from_year(year, types, include_xml)
            for url in urls:
                yield url
                count += 1
                if limit and count >= limit:
                    return

    def _get_legislation_urls_from_type_year(
        self, legislation_type, year, include_xml=True
    ) -> Iterator[str]:
        url = f"{self.base_url}/{legislation_type}/{year}"
        logger.debug(f"Checking URL: {url}")
        res = http_client.get(url)

        # Check if page exists with a reasonable status code
        if res.status_code != 200:
            logger.info(
                f"No {legislation_type} legislation found for year {year} (status: {res.status_code})"
            )
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        # Check for "no results" message or missing content
        no_results_div = soup.find("div", class_="warning")
        if no_results_div and (
            "No items found for" in no_results_div.text
            or "Sorry, but we cannot satisfy your request" in no_results_div.text
        ):
            logger.info(f"No {legislation_type} legislation found for year {year}")
            return []

        next_page = url
        while next_page:
            logger.debug(f"Scraping {next_page}")
            res = http_client.get(next_page)
            soup = BeautifulSoup(res.text, "html.parser")

            hrefs = self._extract_legislation_urls_from_searchpage(soup, legislation_type)

            if hrefs:
                # Filter out URLs that don't return valid XML
                for href in hrefs:
                    xml_url = self._get_data_xml_url_from_content_url(href)
                    if include_xml:
                        yield xml_url
                    else:
                        yield xml_url.replace("/data.xml", "")

            next_page = self._get_next_page_token(soup)

    def _get_next_page_token(self, soup):
        next_page = soup.find("a", title="next page")

        if next_page:
            return self.base_url + next_page["href"]
        else:
            return None

    def _extract_legislation_urls_from_searchpage(self, soup, legislation_type):
        hrefs = []
        valid_endswith = ["/contents/made", "/contents"]

        # Check if content div exists
        content_div = soup.find("div", id="content")
        if not content_div:
            logger.debug(f"No content div found for {legislation_type}")
            return hrefs

        # Check if table exists
        table = content_div.find("table")
        if not table:
            logger.debug(f"No table found for {legislation_type}")
            return hrefs

        # Check if tbody exists
        tbody = table.find("tbody")
        if not tbody:
            logger.debug(f"No tbody found for {legislation_type}")
            return hrefs

        for row in tbody.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue

            cell = cells[0]
            a_tag = cell.find("a")
            if not a_tag or "href" not in a_tag.attrs:
                continue

            href = a_tag["href"]
            if href.startswith(f"/{legislation_type}") and href.endswith(tuple(valid_endswith)):
                # Just store the base URL (without /data.xml) for now
                # We'll validate and process later
                base_url = self.base_url + "/".join(href.split("/")[:-1])
                hrefs.append(base_url)

        return hrefs

    def _get_data_xml_url_from_content_url(self, url):
        """
        Convert a URL like https://www.legislation.gov.uk/ukpga/2022/1
        to a data.xml URL like https://www.legislation.gov.uk/ukpga/2022/1/data.xml

        Args:
            url: Content URL

        Returns:
            Data XML URL
        """
        # Remove any trailing slash
        url = url.rstrip("/")

        # Check if URL already ends with /data.xml
        if url.endswith("/data.xml"):
            return url

        # Check if URL contains /contents - we need to remove this
        if "/contents" in url:
            url = url.split("/contents")[0]

        # Return with /data.xml appended
        return f"{url}/data.xml"

    def _get_historical_urls_from_year(
        self,
        year: int,
        types: list[LegislationType],
        include_xml: bool = True,
    ) -> Iterator[str]:
        """
        Load historical legislation URLs using Atom feeds with year-level caching.

        For pre-1963 years, TNA provides Atom feeds at:
        /primary+secondary/{year}/data.feed

        Historical legislation uses regnal year numbering (e.g., Geo3/41/90)
        but can be discovered by calendar year via Atom feeds.

        CACHING: Results are cached at the year level. When called multiple times
        for the same year (with different type filters), only the first call
        fetches from the Atom feed. Subsequent calls use the cached results.

        Args:
            year: Calendar year (pre-1963)
            types: List of legislation types to filter
            include_xml: Whether to return /data.xml URLs

        Returns:
            Iterator of legislation URLs
        """
        type_values = {t.value for t in types}

        # Check if we've already fetched this year's Atom feed
        if year in self._historical_year_cache:
            logger.debug(f"Using cached Atom feed results for year {year}")
            cached_urls = self._historical_year_cache[year]

            # Filter cached URLs by requested types
            for url, leg_type in cached_urls:
                if leg_type in type_values:
                    yield url
            return

        # Not cached - fetch from Atom feed
        logger.info(f"Discovering historical legislation for year {year} (fetching Atom feed)")

        page = 1
        all_urls = []  # Store ALL URLs for caching (url, type) tuples

        while True:
            # Construct feed URL with pagination
            feed_url = f"{self.base_url}/primary+secondary/{year}/data.feed"
            if page > 1:
                feed_url += f"?page={page}"

            logger.debug(f"Fetching Atom feed: {feed_url}")

            try:
                res = http_client.get(feed_url)
                if res.status_code != 200:
                    logger.warning(
                        f"Failed to fetch Atom feed for year {year}, page {page}: HTTP {res.status_code}"
                    )
                    break

                # Parse Atom XML
                soup = BeautifulSoup(res.text, "xml")

                # Extract entry IDs
                entries = soup.find_all("entry")
                if not entries:
                    logger.debug(f"No entries found in Atom feed for year {year}, page {page}")
                    break

                for entry in entries:
                    id_elem = entry.find("id")
                    if not id_elem:
                        continue

                    # ID format: http://www.legislation.gov.uk/id/ukpga/Geo3/41/90
                    act_id = id_elem.text.strip()

                    # Extract legislation type from ID
                    parts = act_id.split("/")
                    if len(parts) < 5:
                        logger.warning(f"Unexpected ID format: {act_id}")
                        continue

                    leg_type = parts[4]  # e.g., "ukpga", "ukla", "aep"

                    # Convert ID URI to data.xml URL
                    xml_url = act_id.replace("/id/", "/")
                    if include_xml:
                        xml_url += "/data.xml"

                    # Store in cache (url, type) - DON'T filter yet
                    all_urls.append((xml_url, leg_type))

                logger.debug(f"Fetched {len(entries)} entries from year {year}, page {page}")

                # Check for more pages
                more_pages_elem = soup.find("morePages")
                if more_pages_elem:
                    more_pages = int(more_pages_elem.text or "0")
                    if more_pages == 0:
                        break
                else:
                    break

                page += 1

            except Exception as e:
                logger.error(
                    f"Error fetching Atom feed for year {year}, page {page}: {str(e)}",
                    exc_info=True,
                )
                break

        # Cache the results for this year
        self._historical_year_cache[year] = all_urls
        logger.info(f"Cached {len(all_urls)} URLs for year {year} across {page} page(s)")

        # Now filter and yield URLs matching requested types
        filtered_count = 0
        for url, leg_type in all_urls:
            if leg_type in type_values:
                yield url
                filtered_count += 1

        logger.info(
            f"Yielded {filtered_count}/{len(all_urls)} URLs for year {year} matching types {list(type_values)}"
        )

    def _load_legislation_from_url(self, url: str) -> BeautifulSoup:
        res = http_client.get(url)
        soup = BeautifulSoup(res.text, "xml")
        return soup
