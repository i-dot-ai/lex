import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError

from lex.core.exceptions import LexParsingError, ProcessedException
from lex.legislation.models import (
    Commentary,
    CommentaryCitation,
    GeographicalExtent,
    LegislationWithContent,
    Paragraph,
    Schedule,
    Section,
)
from lex.legislation.parser.xml_to_text_parser import CLMLMarkdownParser
from lex.legislation.reference_finders.base import ReferenceFinder
from lex.legislation.reference_finders.pattern import (
    EUReferencePatterns,
    PatternReferenceFinder,
    UKReferencePatterns,
)

logger = logging.getLogger(__name__)


class XMLParser(ABC):
    """Abstract base class for building legislation XML parsers.

    Top level structure: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationCore.xsd
    Main: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationMain.xsd
    """

    def __init__(self, reference_finder: ReferenceFinder):
        self.reference_finder = reference_finder

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
    ) -> Tuple[Dict[str, Section], Dict[str, Schedule], Dict[str, Commentary]]:
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

    def _restrict_extent_to_string(self, extent: str) -> str:
        """Convert the restrict_extent field to a string.
        If the restrict_extent is "E+W+S+N.I.", return "United Kingdom", otherwise return the list of countries separated by commas.

        Args:
            restrict_extent (_type_): The original restrict_extent field, not in a human-readable format.

        Returns:
            extent_str: The converted restrict_extent field, in a human-readable format.
        """
        mapping = {
            "E": "England",
            "W": "Wales",
            "S": "Scotland",
            "N.I.": "Northern Ireland",
            "N.I": "Northern Ireland",
            "NI": "Northern Ireland",
        }

        if extent == "E+W+S+N.I.":
            return "United Kingdom"
        elif extent == "E+W+S+N.I":
            return "United Kingdom"
        elif extent == "E+W+S+NI":
            return "United Kingdom"
        elif extent == "":
            return ""
        else:
            return ", ".join([mapping[extent] for extent in extent.split("+")])

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

    def parse(self, soup: BeautifulSoup) -> LegislationWithContent:
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
        sections, schedules, commentaries = self.parse_content(soup)

        # Return Legislation object
        return LegislationWithContent(
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
            sections=list(sections.values()),
            schedules=list(schedules.values()),
            commentaries=commentaries,
        )


class EUXMLParser(XMLParser):
    """Parser for EU legislation XML format.

    Structure: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationStructureEU.xsd
    Content: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationContentsEU.xsd
    """

    def parse_content(
        self, xml_soup: BeautifulSoup
    ) -> Tuple[Dict[str, Section], Dict[str, Schedule], Dict[str, Commentary]]:
        sections = {}
        schedules = {}
        commentaries = {}

        # TODO: Parse EU XML format better
        # Extra EU Metadata
        # EUPreamble
        # EUBody
        # Schedules
        # Amendments

        # Extract Extent from "Part" element
        leg = xml_soup.find("Legislation")
        extent = leg.get("RestrictExtent")
        legislation_id = leg.get("IdURI")

        # Extract sections from the body
        body = xml_soup.find("EUBody")
        for div_elem in body.find_all("P1", attrs={"IdURI": True}):
            section = self._parse_division(div_elem, extent, legislation_id)
            sections[section.id] = section

            # Extract schedules from the body with citable Ids
        schedule_body = xml_soup.find("Schedules")
        if schedule_body:
            for schedule_elem in schedule_body.find_all("Schedule", attrs={"IdURI": True}):
                try:
                    schedule = self._parse_schedule(schedule_elem, extent, legislation_id)
                    schedules[schedule.id] = schedule
                except LexParsingError as e:
                    logger.error(f"Missing ID Error: {e}")

        # Extract and parse commentaries
        commentary = xml_soup.find("Commentaries")
        if commentary:
            for commentary_elem in commentary.find_all("Commentary", attrs={"id": True}):
                commentary = self._parse_commentary(commentary_elem)
                commentaries[commentary.id] = commentary

        return sections, schedules, commentaries

    def _parse_division(self, element: Tag, extent: str, legislation_id: str) -> Section:
        """Parse a division element."""

        # Get the parent element (similar to p1_group_element in UK parser)
        p1_group_element = element.parent

        # Extract title from parent element
        title = self._extract_text(p1_group_element.find("Title"))

        # Use markdown parser for text extraction (similar to UK parser)
        text = self.markdown_parser.parse_element(p1_group_element).lstrip("\n")

        section = Section(
            id=element.get("IdURI"),  # id or IdURI
            uri=element.get("DocumentURI"),
            number=self._extract_text(element.find("Pnumber")).strip("."),
            title=title,
            text=text,
            extent=self.map_extent(extent),
            paragraphs=[],
            citations=[],
            legislation_id=legislation_id,
        )

        # Parse paragraphs
        for p_elem in element.find_all(
            "P", attrs={"IdURI": True}
        ):  # P1para works but doesn't have ID
            paragraph = self._parse_paragraph(p_elem, legislation_id)
            section.add_paragraph(paragraph)

        # Find references in title
        section.references = self.reference_finder.find_references(section.id, section.text)

        return section

    def _parse_paragraph(self, element: Tag, legislation_id: str) -> Paragraph:
        """Parse a paragraph element."""
        para_id = element.get("IdURI")
        text = self._extract_text(element)
        paragraph = Paragraph(
            id=para_id,
            uri=element.get("DocumentURI"),
            number=str(element.parent.find_all("P").index(element) + 1),
            text=text,
            legislation_id=legislation_id,
            paragraph_id=element.get("id"),
        )

        # Find references
        paragraph.references = self.reference_finder.find_references(para_id, text)

        # Find commentary references
        paragraph.commentary_refs = self._parse_commentary_refs(element)

        return paragraph

    def _parse_schedule(self, element: Tag, extent: str, legislation_id: str) -> Section:
        """Parse a section element."""

        # Get title for schedule if available (improved title extraction)
        if self._extract_text(element.find("Title")):
            schedule_title = self._extract_text(element.find("Title"))
            schedule_text = self.markdown_parser.parse_element(element).lstrip("\n")
        else:
            schedule_title = ""
            schedule_text = ""

        schedule = Schedule(
            id=element.get("IdURI"),
            uri=element.get("DocumentURI"),
            number=self._extract_text(element.find("Pnumber")).strip("."),
            title=schedule_title,
            text=schedule_text,
            extent=self.map_extent(extent),
            paragraphs=[],
            citations=[],
            legislation_id=legislation_id,
        )

        # Parse text from the schedule
        for p1_elem in element.find_all(
            "P", attrs={"IdURI": True}
        ):  # The text body is actually contained within "tbody" so this doesn't return anything
            try:
                paragraph = self._parse_paragraph(p1_elem, legislation_id)
                schedule.add_paragraph(paragraph)

            except LexParsingError as e:
                logger.error(f"Missing ID Error: {e}")

        # Find references in title text
        schedule.references = self.reference_finder.find_references(schedule.id, schedule.text)

        return schedule

    def _parse_commentary(self, element: Tag) -> Commentary:
        """
        Parse a commentary containing element.
        https://legislation.github.io/clml-schema/userguide.html#commentaries
        """

        # Extract type
        commentary_type = element.get("Type")

        # Higher level citations
        citation_elements = element.find_all(
            "Citation", attrs={"URI": True}
        )  # Here we can either make it so attrs is also 'id' or we can substitute ID with the URI, or use parent id?
        citations = []
        for citation in citation_elements:
            try:
                citation = CommentaryCitation(
                    id=citation.get(
                        "id", citation.get("URI")
                    ),  # This is a temporary fix, we need to decide whether to use URI or ID
                    uri=citation.get("URI"),
                    type=commentary_type,
                    context=citation.text,
                )
                citations.append(citation)
            except ValidationError as e:
                logger.warning(
                    f"Skipping invalid citation in commentary: {e}",
                    extra={
                        "citation_uri": citation.get("URI"),
                        "commentary_type": commentary_type,
                        "error_type": "ValidationError",
                    },
                )

        # Lower level citation
        citation_subref_elements = element.find_all("CitationSubRef", attrs={"URI": True})
        for citation_sub_ref in citation_subref_elements:
            try:
                citation_sub_ref = CommentaryCitation(
                    id=citation_sub_ref.get(
                        "id", citation_sub_ref.get("URI")
                    ),  # Fallback to URI if id is missing
                    uri=citation_sub_ref.get("URI"),
                    type=commentary_type,
                    context=citation_sub_ref.text,
                )
                citations.append(citation_sub_ref)
            except ValidationError as e:
                logger.warning(
                    f"Skipping invalid citation subref in commentary: {e}",
                    extra={
                        "citation_uri": citation_sub_ref.get("URI"),
                        "commentary_type": commentary_type,
                        "error_type": "ValidationError",
                    },
                )

        commentary = Commentary(
            id=element.get("id"),
            type=commentary_type,
            citations=citations,
            text=self._extract_text(element),
        )

        return commentary

    def _parse_commentary_refs(self, element: Tag) -> List[str]:
        """Extract citations from the element."""

        commentary_refs = []
        for commentary_ref in element.find_all("CommentaryRef", attrs={"Ref": True}):
            commentary_refs.append(commentary_ref.get("Ref"))

        return commentary_refs


class UKXMLParser(XMLParser):
    """Parser for UK legislation XML format.

    Structure: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationStructure.xsd
    Content: https://github.com/legislation/clml-schema/blob/main/schema/schemaLegislationContents.xsd
    """

    def parse_content(
        self, xml_soup: BeautifulSoup
    ) -> Tuple[Dict[str, Section], Dict[str, Schedule], Dict[str, Commentary]]:
        sections = {}
        schedules = {}
        commentaries = {}

        # Extract metadata
        legislation_id = xml_soup.find("Legislation").get("IdURI")

        extent = xml_soup.find("Legislation").get("RestrictExtent", "")

        # Extract and parse sections from the body with citable Ids
        body = xml_soup.find("Body")
        if not body:
            raise ProcessedException("This legislation only exists as a PDF, not as XML")
        for section_elem in body.find_all("P1", attrs={"IdURI": True}):
            section = self._parse_section(section_elem, extent, legislation_id)
            sections[section.id] = section

        # Extract and parse schedules from the body with citable Ids
        schedule_body = xml_soup.find("Schedules")
        if schedule_body:
            extent = schedule_body.get("RestrictExtent", extent)
            for schedule_elem in schedule_body.find_all("Schedule", attrs={"IdURI": True}):
                schedule = self._parse_schedule(schedule_elem, extent, legislation_id)
                schedules[schedule.id] = schedule

        # Extract and parse commentaries
        commentary = xml_soup.find("Commentaries")
        if commentary:
            for commentary_elem in commentary.find_all("Commentary", attrs={"id": True}):
                commentary = self._parse_commentary(commentary_elem)
                commentaries[commentary.id] = commentary

        return sections, schedules, commentaries

    def _parse_schedule(self, element: Tag, extent: str, legislation_id: str) -> Schedule:
        """Parse a schedule element."""

        # Get title for schedule if available
        if self._extract_text(element.find("Title")):
            schedule_title = self._extract_text(element.find("Title"))
            schedule_text = self.markdown_parser.parse_element(element).lstrip("\n")
        else:
            schedule_title = ""
            schedule_text = ""

        schedule = Schedule(
            id=element.get("IdURI"),
            uri=element.get("DocumentURI"),
            number=element.get("id").lstrip("schedule-").strip("."),
            title=schedule_title,
            text=schedule_text,
            extent=self.map_extent(extent),
            legislation_id=legislation_id,
        )

        # Parse paragraphs with citable Ids
        for p1_elem in element.find_all("P1", attrs={"IdURI": True}):
            paragraph = self._parse_paragraph(p1_elem, legislation_id)
            schedule.add_paragraph(paragraph)

        # Find references in title text
        schedule.references = self.reference_finder.find_references(schedule.id, schedule.text)

        # Find commentary refs for the schedule object
        schedule.commentary_refs = self._parse_commentary_refs(element)

        return schedule

    def _parse_section(self, element: Tag, extent: str, legislation_id: str) -> Section:
        """Parse a section element."""

        p1_group_element = element.parent

        # Try to get local extent, fall back to global extent
        local_extent = self._get_parent_extent(element) or extent

        title = self._extract_text(p1_group_element.find("Title"))

        text = self.markdown_parser.parse_element(p1_group_element).lstrip("\n")

        section = Section(
            id=element.get("IdURI"),
            uri=element.get("DocumentURI"),
            number=element.get("id").lstrip("section-").strip("."),
            title=title,
            text=text,
            extent=self.map_extent(local_extent),
            legislation_id=legislation_id,
        )

        # Parse paragraphs with citable Ids
        # Note that this will only include citable paragraphs.
        # Some, notably paragraphs that do amendments, will not be included.
        for p2_elem in element.find_all(["P2"], recursive=True, attrs={"IdURI": True}):
            paragraph = self._parse_paragraph(p2_elem, legislation_id)
            section.add_paragraph(paragraph)

        # Find references in title text
        section.references = self.reference_finder.find_references(section.id, section.text)

        # Find commentary refs for the section itself
        section.commentary_refs = self._parse_commentary_refs(element)

        return section

    def _parse_nested_commentaries(self, element: Tag, paragraph: Paragraph) -> List[Commentary]:
        """Find nested P3 paragraphs and extract their commentary."""

        nested_p3_paragraphs = element.find_all("P3", recursive=True, attrs={"IdURI": True})
        for nested_p3_paragraphs in nested_p3_paragraphs:
            if nested_p3_paragraphs and nested_p3_paragraphs.find("P3para"):
                for p3_para in nested_p3_paragraphs.find_all("P3para", recursive=True):
                    if p3_para:
                        text = self._extract_text(p3_para)
                        if text:
                            paragraph.references.extend(
                                self.reference_finder.find_references(
                                    paragraph.id, self._extract_text(p3_para)
                                )
                            )
                        if isinstance(
                            p3_para, Tag
                        ):  # Check if the element is a tag, otherwise it's a string
                            p3_commentary = self._parse_commentary_refs(p3_para)
                            paragraph.commentary_refs.extend(p3_commentary)
        return paragraph

    def _parse_paragraph(self, element: Tag, legislation_id: str) -> Paragraph:
        """Parse a paragraph element preserving exact text structure."""

        # Get the main text content
        text_parts = []

        # Add the main paragraph text
        p2para = element.find_all("P2para")
        if p2para:
            for p2p in p2para:
                text_parts.append(self._extract_text(p2p))

        # Process any bullet lists
        for list_elem in element.find_all("UnorderedList"):
            for item in list_elem.find_all("ListItem"):
                text_parts.append(f"* {self._extract_text(item)}")

        # Create paragraph with proper formatting
        text = "\n".join(text_parts)
        paragraph = Paragraph(
            id=element.get("IdURI"),
            uri=element.get("DocumentURI"),
            number=self._extract_text(element.find("Pnumber")).strip("."),
            text=text,
            legislation_id=legislation_id,
            paragraph_id=element.get(
                "id"
            ),  # E.g., "section-1-3-c" for linking to commentary/labelling
        )

        # Find commentary references
        paragraph.commentary_refs = self._parse_commentary_refs(element)

        # Find references
        paragraph.references = self.reference_finder.find_references(paragraph.id, text)

        paragraph = self._parse_nested_commentaries(element, paragraph)

        return paragraph

    def _parse_commentary(self, element: Tag) -> Commentary:
        """
        Parse a commentary containing element.
        https://legislation.github.io/clml-schema/userguide.html#commentaries
        """

        # Extract type
        commentary_type = element.get("Type")

        # Higher level citations
        citation_elements = element.find_all("Citation", attrs={"URI": True})
        citations = []
        for citation in citation_elements:
            try:
                citation = CommentaryCitation(
                    id=citation.get("id", citation.get("URI")),  # Fallback to URI if id is missing
                    uri=citation.get("URI"),
                    type=commentary_type,
                    context=citation.text,
                    section_ref=citation.get("SectionRef", citation.get("StartSectionRef")),
                    citation_ref=citation.get("CitationRef", "SelfReference"),
                    citation_type="primary",
                )
                citations.append(citation)
            except ValidationError as e:
                logger.warning(
                    f"Skipping invalid citation in commentary: {e}",
                    extra={
                        "citation_uri": citation.get("URI"),
                        "commentary_type": commentary_type,
                        "error_type": "ValidationError",
                    },
                )

        # Lower level citation
        citation_subref_elements = element.find_all("CitationSubRef", attrs={"URI": True})
        for citation_sub_ref in citation_subref_elements:
            try:
                citation_sub_ref = CommentaryCitation(
                    id=citation_sub_ref.get(
                        "id", citation_sub_ref.get("URI")
                    ),  # Fallback to URI if id is missing
                    uri=citation_sub_ref.get("URI"),
                    type=commentary_type,
                    context=citation_sub_ref.text,
                    section_ref=citation_sub_ref.get(
                        "SectionRef", citation_sub_ref.get("StartSectionRef")
                    ),
                    citation_ref=citation_sub_ref.get("CitationRef", "SelfReference"),
                    citation_type="sub_reference",
                )
                citations.append(citation_sub_ref)
            except ValidationError as e:
                logger.warning(
                    f"Skipping invalid citation subref in commentary: {e}",
                    extra={
                        "citation_uri": citation_sub_ref.get("URI"),
                        "commentary_type": commentary_type,
                        "error_type": "ValidationError",
                    },
                )

        commentary = Commentary(
            id=element.get("id"),
            type=commentary_type,
            citations=citations,
            text=self._extract_text(element),
        )

        return commentary

    def _parse_commentary_refs(self, element: Tag) -> List[str]:
        """Extract citations from the element."""

        commentary_refs = []
        for commentary_ref in element.find_all(
            ["CommentaryRef"], recursive=True, attrs={"Ref": True}
        ):
            commentary_refs.append(commentary_ref.get("Ref"))
        return commentary_refs

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
            return EUXMLParser(PatternReferenceFinder(EUReferencePatterns()))
        return UKXMLParser(PatternReferenceFinder(UKReferencePatterns()))

    def parse(self, xml_content: str) -> LegislationWithContent:
        """Parse legislation XML content."""
        parser = self.create_parser(xml_content)
        return parser.parse(xml_content)
