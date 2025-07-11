import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from lex.core.exceptions import LexParsingError, PDFParsingException
from lex.legislation.models import (
    GeographicalExtent,
    Legislation,
    LegislationSection,
    ProvisionType,
)
from lex.legislation.parser.xml_to_text_parser import CLMLMarkdownParser

logger = logging.getLogger(__name__)


class XMLParser(ABC):
    """Abstract base class for building legislation XML parsers.

    Top level structure: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationCore.xsd
    Main: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationMain.xsd
    """

    def __init__(self):
        self.extent_mapping = {
            "E": GeographicalExtent.E,
            "W": GeographicalExtent.W,
            "S": GeographicalExtent.S,
            "N.I.": GeographicalExtent.NI,
            "NI": GeographicalExtent.NI,
            "E+W+S+N.I.": GeographicalExtent.UK,
            "E+W+S+N.I": GeographicalExtent.UK,
            "E+W+S+NI": GeographicalExtent.UK,
        }

        self.markdown_parser = CLMLMarkdownParser()

    @abstractmethod
    def parse_content(
        self, xml_soup: BeautifulSoup
    ) -> Tuple[List[LegislationSection], List[LegislationSection]]:
        """Parse XML content into sections."""
        pass

    def _extract_text(self, element: Optional[Tag]) -> str:
        """Extract text from an element, handling None cases and cleaning text."""
        if element is None:
            return ""

        # Remove emphasis, strong and uppercase tags
        for tag in element.find_all(["Emphasis", "Strong", "Uppercase"]):
            tag.unwrap()

        # Get all text content
        text_parts = []
        for text in element.stripped_strings:
            cleaned = self._clean_text(text)
            if cleaned:
                text_parts.append(cleaned)

        content_str = " ".join(text_parts).strip("\n")

        # Remove trailing space before punctuation
        if content_str[-2:] in {" .", " ,"}:
            content_str = content_str[:-2] + content_str[-1]

        return content_str

    def _extract_date(self, element: Tag) -> Optional[date]:
        """Extract date from XML element."""
        text = self._extract_text(element)

        if not text:
            return None

        return datetime.strptime(text, "%Y-%m-%d").date()

    def _extract_value(self, element: Tag) -> str:
        """Extract value from XML element."""
        if element is None:
            return ""
        return element.get("Value", "")

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        # Remove extra whitespace and normalize spaces
        text = " ".join(text.split())
        # Remove common XML artifacts
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        return text

    def map_extent(self, extent: str) -> List[GeographicalExtent]:
        """Convert the extent content field to a unoform string.

        Args:
            extent (str): The original restrict_extent field, not in a human-readable format.

        Returns:
            extent_str: The converted restrict_extent field, in a human-readable format.
        """

        try:
            if extent in self.extent_mapping:
                return [self.extent_mapping[extent]]
            elif extent == "":
                return [GeographicalExtent.NONE]
            elif extent is None:
                return [GeographicalExtent.NONE]
            else:
                return [self.extent_mapping[extent] for extent in extent.split("+")]
        except KeyError:
            return [GeographicalExtent.NONE]
        except Exception as e:
            logger.error(f"Unkown Extent Mapping Error: {e}")
            return [GeographicalExtent.NONE]

    def parse(self, soup: BeautifulSoup) -> Tuple[Legislation, List[LegislationSection], List[LegislationSection]]:
        """Parse XML content into a Legislation object."""

        # Extract the standard metadata
        id = soup.find("Legislation").get("IdURI")
        uri = self._extract_text(soup.find("dc:identifier"))
        title = self._extract_text(soup.find("dc:title"))
        description = self._extract_text(soup.find("dc:description"))
        valid_date = self._extract_date(soup.find("dct:valid"))
        modified_date = self._extract_date(soup.find("dc:modified"))
        publisher = self._extract_text(soup.find("dc:publisher"))
        category = self._extract_value(soup.find("ukm:DocumentCategory"))
        type = id.split("/")[4]
        year = self._extract_value(soup.find("ukm:Year"))
        number = self._extract_value(soup.find("ukm:Number"))
        status = self._extract_value(soup.find("ukm:DocumentStatus"))

        legislation_element = soup.find("Legislation")
        if legislation_element.has_attr("NumberOfProvisions"):
            number_of_provisions = legislation_element["NumberOfProvisions"]
        else:
            number_of_provisions = None
        if legislation_element.has_attr(
            "RestrictExtent"
        ):  # Check if restrict extent is present. Unclear why some of the XMLs have it and some don't
            extent = legislation_element["RestrictExtent"]
        else:
            extent = ""

        enactment_date = soup.find("ukm:EnactmentDate")
        if enactment_date is not None:
            enactment_date = datetime.strptime(
                enactment_date.get("Date"), "%Y-%m-%d"
            ).date()  # Made / Laid for secondary?

        # Parse content into sections, schedules and citations
        sections, schedules = self.parse_content(soup)

        # Return Legislation object
        legislation = Legislation(
            id=id,
            uri=uri,
            title=title,
            description=description,
            enactment_date=enactment_date,
            valid_date=valid_date,
            modified_date=modified_date,
            publisher=publisher,
            category=category,
            type=type,
            year=year,
            number=number,
            status=status,
            extent=self.map_extent(extent),
            number_of_provisions=int(number_of_provisions),
        )

        return legislation, sections, schedules

class EUXMLParser(XMLParser):
    """Parser for EU legislation XML format.

    Structure: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationStructureEU.xsd
    Content: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationContentsEU.xsd
    """

    def parse_content(
        self, xml_soup: BeautifulSoup
    ) -> Tuple[Dict[str, LegislationSection], Dict[str, LegislationSection]]:
        sections = []
        schedules = []

        # Extract Extent from "Part" element
        leg = xml_soup.find("Legislation")
        extent = leg.get("RestrictExtent")
        legislation_id = leg.get("IdURI")

        # Extract sections from the body
        body = xml_soup.find("EUBody")
        for div_elem in body.find_all("P1", attrs={"IdURI": True}):
            section = self._parse_division(div_elem, extent, legislation_id)
            sections.append(section)

            # Extract schedules from the body with citable Ids
        schedule_body = xml_soup.find("Schedules")
        if schedule_body:
            for schedule_elem in schedule_body.find_all("Schedule", attrs={"IdURI": True}):
                try:
                    schedule = self._parse_schedule(schedule_elem, extent, legislation_id)
                    schedules.append(schedule)
                except LexParsingError as e:
                    logger.error(f"Missing ID Error: {e}")

        return sections, schedules

    def _parse_division(self, element: Tag, extent: str, legislation_id: str) -> LegislationSection:
        """Parse a division element."""

        # Get the parent element (similar to p1_group_element in UK parser)
        p1_group_element = element.parent

        # Extract title from parent element
        title = self._extract_text(p1_group_element.find("Title"))

        # Use markdown parser for text extraction (similar to UK parser)
        text = self.markdown_parser.parse_element(p1_group_element).lstrip("\n")

        section = LegislationSection(
            id=element.get("IdURI"),
            uri=element.get("DocumentURI"),
            legislation_id=legislation_id,
            title=title,
            text=text,
            extent=self.map_extent(extent),
            provision_type=ProvisionType.SECTION,
        )

        return section

    def _parse_schedule(self, element: Tag, extent: str, legislation_id: str) -> LegislationSection:
        """Parse a section element."""

        # Get title for schedule if available (improved title extraction)
        if self._extract_text(element.find("Title")):
            schedule_title = self._extract_text(element.find("Title"))
            schedule_text = self.markdown_parser.parse_element(element).lstrip("\n")
        else:
            schedule_title = ""
            schedule_text = ""

        schedule = LegislationSection(
            id=element.get("IdURI"),
            uri=element.get("DocumentURI"),
            legislation_id=legislation_id,
            title=schedule_title,
            text=schedule_text,
            extent=self.map_extent(extent),
            provision_type=ProvisionType.SCHEDULE,
        )

        return schedule

class UKXMLParser(XMLParser):
    """Parser for UK legislation XML format.

    Structure: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationStructure.xsd
    Content: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationContents.xsd
    """

    def parse_content(
        self, xml_soup: BeautifulSoup
    ) -> Tuple[Dict[str, LegislationSection], Dict[str, LegislationSection]]:
        sections = []
        schedules = []

        # Extract metadata
        legislation_id = xml_soup.find("Legislation").get("IdURI")

        extent = xml_soup.find("Legislation").get("RestrictExtent", "")

        # Extract and parse sections from the body with citable Ids
        body = xml_soup.find("Body")
        if not body:
            raise PDFParsingException("This legislation only exists as a PDF, not as XML")
        for section_elem in body.find_all("P1", attrs={"IdURI": True}):
            section = self._parse_section(section_elem, extent, legislation_id)
            sections.append(section)

        # Extract and parse schedules from the body with citable Ids
        schedule_body = xml_soup.find("Schedules")
        if schedule_body:
            extent = schedule_body.get("RestrictExtent", extent)
            for schedule_elem in schedule_body.find_all("Schedule", attrs={"IdURI": True}):
                schedule = self._parse_schedule(schedule_elem, extent, legislation_id)
                schedules.append(schedule)

        return sections, schedules

    def _parse_schedule(self, element: Tag, extent: str, legislation_id: str) -> LegislationSection:
        """Parse a schedule element."""

        # Get title for schedule if available
        if self._extract_text(element.find("Title")):
            schedule_title = self._extract_text(element.find("Title"))
            schedule_text = self.markdown_parser.parse_element(element).lstrip("\n")
        else:
            schedule_title = ""
            schedule_text = ""

        schedule = LegislationSection(
            id=element.get("IdURI"),
            uri=element.get("DocumentURI"),
            legislation_id=legislation_id,
            title=schedule_title,
            text=schedule_text,
            extent=self.map_extent(extent),
            provision_type=ProvisionType.SCHEDULE,
        )

        return schedule

    def _parse_section(self, element: Tag, extent: str, legislation_id: str) -> LegislationSection:
        """Parse a section element."""

        p1_group_element = element.parent

        # Try to get local extent, fall back to global extent
        local_extent = self._get_parent_extent(element) or extent

        title = self._extract_text(p1_group_element.find("Title"))

        text = self.markdown_parser.parse_element(p1_group_element).lstrip("\n")

        section = LegislationSection(
            id=element.get("IdURI"),
            uri=element.get("DocumentURI"),
            legislation_id=legislation_id,
            title=title,
            text=text,
            extent=self.map_extent(local_extent),
            provision_type=ProvisionType.SECTION,
        )

        return section

    def _get_parent_extent(self, element: Tag) -> str:
        """Get the RestrictExtent value from the parent Part element."""
        current = element.parent
        while current is not None:
            if current.name == "Part":
                return current.get("RestrictExtent", "")
            current = current.parent
        return ""  # Return empty string if no Part parent found

class LegislationParser:
    """Main interface for parsing legislation documents."""

    @staticmethod
    def create_parser(soup: BeautifulSoup) -> XMLParser:
        """Create appropriate parser based on XML content."""

        if soup.find("EURetained"):
            return EUXMLParser()
        return UKXMLParser()

    def parse(self, xml_content: str) -> Tuple[Legislation, List[LegislationSection], List[LegislationSection]]:
        """Parse legislation XML content."""
        parser = self.create_parser(xml_content)
        return parser.parse(xml_content)
