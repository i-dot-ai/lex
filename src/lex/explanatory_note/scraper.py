import logging
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from lex.core.http import HttpClient
from lex.explanatory_note.models import (
    ExplanatoryNote,
    ExplanatoryNoteSectionType,
    ExplanatoryNoteType,
)
from lex.legislation.models import LegislationType
from lex.legislation.scraper import LegislationScraper

http_client = HttpClient()

logger = logging.getLogger(__name__)

# Explanatory notes do not follow the Scraper Parser structure.
# This is because Explanatory note content is stored across multiple pages and must therefore be scraped iteratively.

# Constants
NOTE_TYPE_MAPPING = {
    # Old style mappings
    "Introduction": "overview",
    "Overview": "overview",
    "Overview of the Act": "overview",
    "Summary": "overview",
    "Background": "overview",
    "Summary and Background": "overview",
    "Background and Summary": "overview",
    "Territorial Application": "extent",
    "Commentary on Sections": "provisions",
    "Commentary": "provisions",
    "Commencement": "commencement",
    # New style mappings
    "Policy background": "policy_background",
    "Legal background": "legal_background",
    "Territorial extent and application": "extent",
    "Section": "provisions",
    "Schedule": "provisions",
    "Part": "provisions",
}


class NoteProcessor:
    """Base class for processing explanatory notes."""

    def __init__(self, legislation_id: str):
        self.base_url = "https://www.legislation.gov.uk"
        self.legislation_id = legislation_id

    def _extract_section_info(
        self, title: str
    ) -> Tuple[Optional[ExplanatoryNoteSectionType], Optional[int]]:
        """
        Extract section type and number from a title.

        Args:
            title: The title to extract information from

        Returns:
            Tuple of (section_type, section_number)
        """
        pattern = r"^(Section|Schedule|Part) (\d+)(?!\d)"
        match = re.match(pattern, title, re.IGNORECASE)
        if match:
            return ExplanatoryNoteSectionType(match.group(1).lower()), int(match.group(2))
        return None, None

    def _post_process_section_text(self, text: str) -> str:
        """
        Clean and format section text.

        Args:
            text: The text to process

        Returns:
            Processed text with proper formatting
        """
        lines = text.split("\n")
        processed_lines = []

        for line in lines:
            leading_tabs = re.match(r"^\t*", line).group()
            line = line.strip()
            if line:
                processed_lines.append(leading_tabs + line)

        text = "\n".join(processed_lines)
        return re.sub(r"\n+", "\n", text)

    def _notes_soup_to_initial_dict(
        self, soup: BeautifulSoup, starting_order: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Convert BeautifulSoup object to initial dictionary format.

        Args:
            soup: BeautifulSoup object containing the notes
            starting_order: The starting order number

        Returns:
            Tuple of (list of section dictionaries, final order number)
        """
        sections = []
        text = ""
        route = [None] * 5
        route[1] = "Introduction"
        order = starting_order

        def append_section():
            nonlocal text, order
            if text:
                sections.append(
                    {
                        "route": [r for r in route if r is not None],
                        "text": self._post_process_section_text(text.strip()),
                        "order": order,
                    }
                )
                text = ""
                order += 1

        for element in soup:
            tag_type = element.name
            tag_text = element.text.strip()

            if tag_type and tag_type.startswith("h") and len(tag_type) == 2:
                level = int(tag_type[1]) - 2
                if 0 <= level < 5:
                    append_section()
                    route[level] = tag_text
                    route[level + 1 :] = [None] * (4 - level)

            elif tag_type in ["p", "blockquote"]:
                if tag_text:
                    text += tag_text + "\n"

            elif tag_type in ["ul", "ol"]:
                for sub_element in element:
                    sub_element_text = sub_element.text.strip()
                    if sub_element_text:
                        text += "\t" + sub_element_text + "\n"

        append_section()
        return sections, order

    def _update_initial_dict(self, notes_initial_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Update the initial dictionary with additional information."""
        notes_initial_dict["legislation_id"] = self.legislation_id
        notes_initial_dict["id"] = f"{self.legislation_id}_{notes_initial_dict['order'] + 1}"

        # Add note type
        for element in notes_initial_dict["route"][::-1]:
            matching_key = next((key for key in NOTE_TYPE_MAPPING.keys() if key in element), None)
            if matching_key:
                notes_initial_dict["note_type"] = ExplanatoryNoteType(
                    NOTE_TYPE_MAPPING[matching_key]
                )
                break

        # Add section info
        for element in notes_initial_dict["route"][::-1]:
            section_type, section_number = self._extract_section_info(element)
            if section_type:
                notes_initial_dict["section_type"] = section_type
                notes_initial_dict["section_number"] = section_number
                break

        return notes_initial_dict


class OldNoteProcessor(NoteProcessor):
    """Processor for old style explanatory notes."""

    def process_sections(self, soup: BeautifulSoup) -> List[ExplanatoryNote]:
        """Process sections from old style notes."""
        notes_page_link = self.base_url + soup.find("a", title="Open Explanatory Notes")["href"]
        notes_page = http_client.get(notes_page_link)
        notes_page_soup = BeautifulSoup(notes_page.content, "html.parser")

        notes_page_soup = notes_page_soup.find("div", class_="LegSnippet")
        sections, _ = self._notes_soup_to_initial_dict(notes_page_soup)
        sections = [self._update_initial_dict(section) for section in sections]
        return [ExplanatoryNote(**section) for section in sections]


class NewNoteProcessor(NoteProcessor):
    """Processor for new style explanatory notes."""

    def _get_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Get the URL of the next page."""
        elements = soup.find_all("a", class_="userFunctionalElement nav")
        for element in elements:
            if element.text.strip() == "Next":
                return urljoin(current_url, element["href"])
        return None

    def _get_all_pages(
        self, contents_page_soup: BeautifulSoup, current_url: str
    ) -> List[BeautifulSoup]:
        """Get all pages of the notes."""
        pages = [contents_page_soup]
        next_page_url = self._get_next_page_url(contents_page_soup, current_url)

        while next_page_url:
            logger.debug(f"Fetching {next_page_url}")
            next_page = http_client.get(next_page_url)
            next_page_soup = BeautifulSoup(next_page.text, "html.parser")
            pages.append(next_page_soup)
            next_page_url = self._get_next_page_url(next_page_soup, next_page_url)

        return pages

    def process_sections(self, soup: BeautifulSoup) -> List[ExplanatoryNote]:
        """Process sections from new style notes."""
        current_url = f"{self.legislation_id}/notes/division/1/index.htm"
        pages = self._get_all_pages(soup, current_url)
        articles = [page.find("article") for page in pages]

        sections = []
        current_order = 0
        for article in articles:
            new_sections, current_order = self._notes_soup_to_initial_dict(article, current_order)
            sections.extend(new_sections)

        sections = [self._update_initial_dict(section) for section in sections]
        return [ExplanatoryNote(**section) for section in sections]


class ExplanatoryNoteScraperAndParser:
    """Scraper for explanatory notes."""

    def __init__(
        self,
        base_url: str = "https://www.legislation.gov.uk",
    ):
        self.base_url = base_url

    def scrape_and_parse_content(
        self, years: list[int], types: list[LegislationType], limit: Optional[int] = None
    ) -> Iterator[tuple[str, ExplanatoryNote]]:
        legislation_scraper = LegislationScraper()

        self.urls = legislation_scraper.load_urls(years, types, limit, include_xml=False)

        for url in self.urls:
            try:
                yield from self._get_explanatory_note_sections(url)
            except Exception as e:
                logger.error(f"Error scraping and parsing explanatory note: {e}", exc_info=True)

    def _get_explanatory_note_contents_soup(self, legislation_id: str) -> Optional[BeautifulSoup]:
        """Get the BeautifulSoup object for the explanatory notes contents page."""

        contents_page_uri = legislation_id + "/contents"
        try:
            landing_page = http_client.get(contents_page_uri)
            landing_page_soup = BeautifulSoup(landing_page.text, "html.parser")

            notes_contents_page_link = landing_page_soup.find("a", string="Explanatory Notes")[
                "href"
            ]
            if not notes_contents_page_link:
                return None

            notes_contents_page_link = self.base_url + notes_contents_page_link
            notes_contents_page = http_client.get(notes_contents_page_link)
            return BeautifulSoup(notes_contents_page.text, "html.parser")
        except (requests.RequestException, TypeError, AttributeError):
            logger.info(f"No explanatory note found for {legislation_id}")
            return None

    def _is_old_explanatory_note_page(self, notes_contents_soup: BeautifulSoup) -> Optional[bool]:
        """Determine if the page is an old style explanatory notes page."""
        try:
            if (
                notes_contents_soup.find("a", title="Open Explanatory Notes").text
                == "Open full notes"
            ):
                return True
        except AttributeError:
            pass

        try:
            if (
                notes_contents_soup.find("article").find("h2", class_="title").text.strip()
                == "What these notes do"
            ):
                return False
        except AttributeError:
            pass

        return None

    def _get_explanatory_note_sections(self, legislation_id: str) -> list[ExplanatoryNote]:
        """Get all explanatory notes sections for a document."""
        explanatory_note_contents_soup = self._get_explanatory_note_contents_soup(legislation_id)

        if not explanatory_note_contents_soup:
            return []

        is_old_page = self._is_old_explanatory_note_page(explanatory_note_contents_soup)
        if is_old_page is None:
            logger.info(
                f"Could not determine the style of the explanatory note page for {legislation_id}.",
                extra={
                    "doc_type": "explanatory_note",
                    "legislation_id": legislation_id,
                    "processing_status": "style_unknown",
                    "note_style": "unknown",
                },
            )
            return []

        processor = (
            OldNoteProcessor(legislation_id) if is_old_page else NewNoteProcessor(legislation_id)
        )
        sections = processor.process_sections(explanatory_note_contents_soup)

        # Update the section legislation_ids to make them match the legislation endpoints

        updated_legislation_id = legislation_id.replace(
            "https://www.legislation.gov.uk/", "http://www.legislation.gov.uk/id/"
        )
        for section in sections:
            section.legislation_id = updated_legislation_id
            section.id = section.id.replace(
                "https://www.legislation.gov.uk/", "http://www.legislation.gov.uk/id/"
            )

        logger.info(
            f"Scraped and parsed {len(sections)} sections for {legislation_id}",
            extra={
                "doc_type": "explanatory_note",
                "legislation_id": legislation_id,
                "processing_status": "success",
                "note_style": "old" if is_old_page else "new",
                "section_count": len(sections),
            },
        )
        ids = [section.id for section in sections]
        return list(zip(ids, sections))
