from bs4 import BeautifulSoup

from lex.core.http import HttpClient

from .loader import LexLoader

http_client = HttpClient()


class LexScraper(LexLoader):
    """Scraper for Lex content."""

    def _load_legislation_from_url(self, url: str) -> BeautifulSoup:
        res = http_client.get(url)
        soup = BeautifulSoup(res.text, "xml")
        return soup
