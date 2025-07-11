from typing import Iterator, Optional

from bs4 import BeautifulSoup

from lex.core.scraper import LexScraper
from lex.legislation.models import LegislationType
from lex.legislation.scraper import LegislationScraper


class ExplanatoryNoteScraper(LexScraper):

    def load_content(
        self, years: list[int], types: list[LegislationType], limit: Optional[int] = None
    ) -> Iterator[tuple[str, BeautifulSoup]]:
        """Loads content, returning a list of urls andBeautifulSoup objects."""
        legislation_scraper = LegislationScraper()
        self.urls = legislation_scraper.load_urls(years, types, limit, include_xml=True)

        for url in self.urls:
            soup = self._load_legislation_from_url(url)
            yield url, soup

