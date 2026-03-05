from abc import ABC, abstractmethod

from lex.legislation.models import FreeTextReference


class ReferenceFinder(ABC):
    """Abstract base class for finding and parsing references in legislative text."""

    @abstractmethod
    def find_references(self, source_id: str, text: str) -> list[FreeTextReference]:
        """Find references in text."""
        pass
