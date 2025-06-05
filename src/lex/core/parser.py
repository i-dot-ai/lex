from abc import ABC, abstractmethod

from bs4 import BeautifulSoup

from .models import LexModel


class LexParser(ABC):
    """Abstract base class for Lex parsers."""

    @abstractmethod
    def parse_content(self, soup: BeautifulSoup) -> LexModel | list[LexModel]:
        """Parse the content of a BeautifulSoup object into a LexModel."""
        pass
