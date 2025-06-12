import logging
from typing import Iterator

from bs4 import BeautifulSoup

from lex.core.http import HttpClient
from lex.core.scraper import LexScraper
from lex.legislation.models import LegislationType

http_client = HttpClient()

logger = logging.getLogger(__name__)


class LegislationScraper(LexScraper):
    def __init__(self):
        self.base_url = "https://www.legislation.gov.uk"

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
        count = 0
        for year in years:
            for type in types:
                urls = self._get_legislation_urls_from_type_year(type.value, year, include_xml)
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

    def _load_legislation_from_url(self, url: str) -> BeautifulSoup:
        res = http_client.get(url)
        soup = BeautifulSoup(res.text, "xml")
        return soup
