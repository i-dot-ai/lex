from abc import ABC, abstractmethod
from typing import Iterator

from bs4 import BeautifulSoup


class LexLoader(ABC):
    """Abstract base class for Lex scrapers."""

    @abstractmethod
    def load_content(
        self, years: list[int] | None = None, limit: int | None = None
    ) -> Iterator[tuple[str, BeautifulSoup]]:
        """Loads content, returning a list of urls andBeautifulSoup objects."""
        pass
