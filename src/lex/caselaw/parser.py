import logging
import re
from typing import Tuple

from bs4 import BeautifulSoup, Tag

from lex.caselaw.models import Caselaw, CaselawSection
from lex.core.exceptions import LexParsingError
from lex.core.parser import LexParser

logger = logging.getLogger(__name__)


class CaselawAndCaselawSectionsParser(LexParser):
    """Parser for caselaw content from the National Archives."""

    def parse_content(self, soup: BeautifulSoup) -> Tuple[Caselaw, list[CaselawSection]]:
        """Parse the content of a BeautifulSoup object into a Caselaw and list of CaselawSection."""
        metadata = self._soup_to_caselaw(soup)
        sections = self._soup_to_sections(soup)

        metadata.text = self._sections_to_text(sections)

        return metadata, sections

    def _sections_to_text(self, sections: list[CaselawSection]) -> str:
        return "\n".join([section.text for section in sections])

    def _soup_to_caselaw(self, soup: BeautifulSoup) -> Caselaw:
        metadata_dict = self._soup_to_caselaw_metadata(soup)
        return Caselaw(**metadata_dict)

    def _soup_to_caselaw_metadata(self, soup: BeautifulSoup) -> Caselaw:
        metadata = soup.find("meta")

        # Find the metadata objects
        try:
            year = metadata.find("proprietary").find("uk:year").text
        except AttributeError:
            year = metadata.find("FRBRExpression").find("FRBRuri")["value"].split("/")[-2]

        try:
            number = metadata.find("proprietary").find("uk:number").text
        except AttributeError:
            number = metadata.find("FRBRExpression").find("FRBRuri")["value"].split("/")[-1]

        try:
            cite = metadata.find("proprietary").find("uk:cite").text
        except AttributeError:
            cite = ""

        metadata_dict = {
            "id": metadata.find("FRBRExpression").find("FRBRuri")["value"],
            "name": metadata.find("FRBRWork").find("FRBRname")["value"],
            "date": metadata.find("FRBRWork").find("FRBRdate")["date"],
            "date_of": metadata.find("FRBRWork").find("FRBRdate")["name"],
            "year": year,
            "number": number,
            "cite_as": cite,
        }

        if metadata_dict["id"] == "https://caselaw.nationalarchives.gov.uk/":
            raise LexParsingError("Invalid caselaw id, the underlying metadata is missing")

        # Find the court and division. We parse this from the url to be consistent with the url definitions.
        metadata_dict.update(self._parse_case_url(metadata_dict["id"]))

        # Find the header
        metadata_dict["header"] = self._soup_to_header(soup)

        # Discover the references
        metadata_dict["caselaw_references"] = self._parse_references(soup, "case")
        metadata_dict["legislation_references"] = self._parse_references(soup, "legislation")

        return metadata_dict

    def _parse_references(self, soup: BeautifulSoup, reference_type: str) -> list[str]:
        references = soup.find_all("ref", {"uk:type": reference_type})
        return [ref["href"] for ref in references if ".gov.uk" in ref["href"]]

    def _parse_case_url(self, url: str) -> dict:
        pattern = r"https://caselaw\.nationalarchives\.gov\.uk/([^/]+)(?:/([^/]+))?/\d{4}/\d+"
        match = re.match(pattern, url)

        if match:
            court = match.group(1)
            division = match.group(2) if match.group(2) else None
            return {
                "court": court.lower(),
                "division": division.lower() if division else None,
            }
        return {}

    def _soup_to_header(self, soup: BeautifulSoup) -> str:
        header = soup.find("header")
        header_lines = header.text.splitlines()
        header_lines = [
            line for line in header_lines if "- - - - - - - - - - - - - - - - -" not in line
        ]
        header_lines = [line.strip() for line in header_lines if line.strip() != ""]
        return "\n".join(header_lines)

    def _soup_to_sections(self, soup: BeautifulSoup) -> list[CaselawSection]:
        type_to_function = {
            "nested_levels": self._soup_to_sections_nested_levels,
            "flat_paragraphs": self._soup_to_sections_flat_paragraphs,
            "quote_levels": self._soup_to_sections_quote,
            "levels_and_paragraphs": self._soup_to_sections_levels_and_paragraphs,
            "default": self._soup_to_sections_default,
        }

        caselaw_section_type = self._get_caselaw_section_type(soup)
        logger.debug(f"Processing caselaw section type: {caselaw_section_type}")

        caselaw_metadata = self._soup_to_caselaw_metadata(soup)

        try:
            sections_dict = type_to_function[caselaw_section_type](soup)
            sections_dict = [caselaw_metadata | section_dict for section_dict in sections_dict]
            sections = [CaselawSection(**section_dict) for section_dict in sections_dict]

        except Exception:
            logger.error(
                f"Error processing caselaw section type: {caselaw_section_type}",
                exc_info=True,
            )
            sections_dict = self._soup_to_sections_default(soup)
            sections_dict = [section_dict | caselaw_metadata for section_dict in sections_dict]
            sections = [CaselawSection(**section_dict) for section_dict in sections_dict]

        return sections

    def _get_caselaw_section_type(self, soup: BeautifulSoup) -> str:
        non_recursive_elements = (
            soup.find("judgmentBody")
            .find("decision")
            .find_all(["level", "paragraph"], recursive=False)
        )
        recursive_elements = (
            soup.find("judgmentBody")
            .find("decision")
            .find_all(["level", "paragraph"], recursive=True)
        )

        if all(element.name == "level" for element in non_recursive_elements):
            return "nested_levels"

        elif all(element.name == "paragraph" for element in non_recursive_elements[1:]):
            return "flat_paragraphs"

        elif soup.find("p", class_="Quote") is not None:
            return "quote_levels"

        elif len(recursive_elements) == len(non_recursive_elements):
            levels = [element for element in recursive_elements if element.name == "level"]
            level_text = [self._element_to_text(element) for element in levels[1:-1]]
            max_label_length = 100
            has_short_labels = all(len(label) < max_label_length for label in level_text)

            if has_short_labels:
                return "levels_and_paragraphs"

        return "default"

    def _element_to_text(self, element: Tag) -> str:
        return element.text.strip().replace("\n\n", "")

    def _soup_to_caselaw_id_decision(self, soup: BeautifulSoup) -> tuple[str, BeautifulSoup]:
        caselaw_id = soup.find("meta").find("FRBRExpression").find("FRBRuri")["value"]
        decision = soup.find("judgmentBody").find("decision")
        return caselaw_id, decision

    def _soup_to_sections_nested_levels(self, soup: BeautifulSoup) -> list[dict]:
        caselaw_id, decision = self._soup_to_caselaw_id_decision(soup)
        route = []
        sections = []
        order = 1

        for level in decision.find_all(["level"], recursive=False):
            heading = level.find("heading")
            if heading:
                heading_text = self._element_to_text(heading)
                if self._is_level_underline(heading) or not route:
                    route = [heading_text]
                else:
                    route = [route[0]] + [heading_text]
            else:
                continue

            paragraphs = level.find_all("paragraph")

            for paragraph in paragraphs:
                sections.append(
                    {
                        "caselaw_id": caselaw_id,
                        "route": route.copy(),
                        "text": self._element_to_text(paragraph),
                        "order": order,
                        "id": f"{caselaw_id}-{order}",
                    }
                )
                order += 1

        return sections

    def _soup_to_sections_flat_paragraphs(self, soup: BeautifulSoup) -> list[dict]:
        caselaw_id, decision = self._soup_to_caselaw_id_decision(soup)
        route = []
        sections = []
        order = 1

        def subparagraph_has_num_tag(subparagraph: Tag) -> bool:
            return subparagraph.find("num") is not None

        for element in decision.find_all(["paragraph", "subparagraph"], recursive=True):
            previous_section_text = sections[-1]["text"] if sections else ""

            if element.name == "paragraph":
                element_text = self._element_to_text(element)
                if element_text not in previous_section_text:
                    sections.append(
                        {
                            "caselaw_id": caselaw_id,
                            "route": route.copy(),
                            "text": element_text,
                            "order": order,
                            "id": f"{caselaw_id}-{order}",
                        }
                    )
                    order += 1

            elif element.name == "subparagraph":
                if not subparagraph_has_num_tag(element) and self._is_level_bold(element):
                    element_text = self._element_to_text(element)
                    route = [element_text]

        return sections

    def _soup_to_sections_quote(self, soup: BeautifulSoup) -> list[dict]:
        caselaw_id, decision = self._soup_to_caselaw_id_decision(soup)
        sections = []
        route = []
        order = 1
        current_text = ""

        # Helper function to add the current section to the list
        def add_current_section():
            nonlocal current_text, order
            if current_text.strip():  # Only add if there's actual content
                sections.append(
                    {
                        "caselaw_id": caselaw_id,
                        "route": route.copy(),  # Make a copy to avoid reference issues
                        "text": current_text.strip(),
                        "order": order,
                        "id": f"{caselaw_id}-{order}",
                    }
                )
                order += 1
                current_text = ""

        for element in decision.find_all(["level", "paragraph"], recursive=False):
            if element.name == "level" and not self._is_class_quote(element):
                # When we find a new route, add any accumulated text as a section first
                add_current_section()
                # Then update the route for future content
                route = [self._element_to_text(element)]

            elif element.name == "level" and self._is_class_quote(element):
                # For quote levels, just accumulate the text under current route
                if current_text:
                    current_text += "\n"
                current_text += self._element_to_text(element)

            elif element.name == "paragraph":
                # For paragraphs, accumulate the text under current route
                if current_text:
                    current_text += "\n"
                current_text += self._element_to_text(element)
                # Create a section for this paragraph's content
                add_current_section()

        # Don't forget any trailing content
        add_current_section()

        return sections

    def _soup_to_sections_default_archive(self, soup: BeautifulSoup) -> list[dict]:
        caselaw_id, decision = self._soup_to_caselaw_id_decision(soup)
        sections = []
        route = []
        order = 1

        for element in decision.find_all(["paragraph"], recursive=False):
            sections.append(
                {
                    "caselaw_id": caselaw_id,
                    "route": route,
                    "text": self._element_to_text(element),
                    "order": order,
                    "id": f"{caselaw_id}-{order}",
                }
            )
            order += 1

        return [CaselawSection(**section) for section in sections]

    def _soup_to_sections_levels_and_paragraphs(self, soup: BeautifulSoup) -> list[dict]:
        caselaw_id, decision = self._soup_to_caselaw_id_decision(soup)
        sections = []
        route = []
        order = 1

        for element in decision.find_all(["level", "paragraph"], recursive=False):
            element_text = self._element_to_text(element)
            if element.name == "level":
                route = [element_text]

            elif element.name == "paragraph":
                sections.append(
                    {
                        "caselaw_id": caselaw_id,
                        "route": route,
                        "order": order,
                        "text": element_text,
                        "id": f"{caselaw_id}-{order}",
                    }
                )
                order += 1

        return sections

    def _soup_to_sections_default(self, soup: BeautifulSoup) -> list[dict]:
        caselaw_id, decision = self._soup_to_caselaw_id_decision(soup)
        text = decision.text
        paragraphs = self._text_to_paragraphs(text)

        paragraphs_dict = [
            {
                "caselaw_id": caselaw_id,
                "route": [],
                "id": f"{caselaw_id}-{i + 1}",
                "order": i,
                "text": paragraph,
            }
            for i, paragraph in enumerate(paragraphs)
        ]

        return paragraphs_dict

    def _text_to_paragraphs(self, text: str) -> list[str]:
        # Remove duplicate newline characters
        text = re.sub(r"\n+", "\n", text)
        # Remove newline characters after bullet points
        text = re.sub(r"•\n", "•", text)

        # Replace anything like i) or a) or (1) with i. or a. or 1.
        text = re.sub(r"([a-z0-9])[\)]", r"\1.", text)
        text = re.sub(r"\(([a-z0-9])", r"\1", text)

        def remove_newline_after_markers(text):
            pattern = r"([ivxlcdm]+|[a-z])\.\n"

            def replace_func(match):
                return match.group()[:-1]

            return re.sub(pattern, replace_func, text, flags=re.IGNORECASE)

        text = remove_newline_after_markers(text)

        def split_text(text):
            pattern = r"(\d+)\.\n"
            matches = list(re.finditer(pattern, text))
            sections = []
            last_end = 0
            expected_number = 1

            for match in matches:
                number = int(match.group(1))
                if number == expected_number:
                    section_text = (
                        f"{expected_number - 1}.\n" + text[last_end : match.start()].strip()
                    )
                    if section_text:
                        sections.append(section_text)
                    last_end = match.end()
                    expected_number += 1

            section_text = f"{expected_number - 1}.\n" + text[last_end:].strip()
            if section_text:
                sections.append(section_text)

            return sections

        return split_text(text)

    def _is_level_bold(self, element: Tag) -> bool:
        bold_span = element.find("span", style=lambda value: value and "font-weight:bold" in value)
        return bold_span is not None

    def _is_level_italic(self, element: Tag) -> bool:
        italic_span = element.find(
            "span", style=lambda value: value and "font-style:italic" in value
        )
        return italic_span is not None

    def _is_level_underline(self, element: Tag) -> bool:
        underline_span = element.find(
            "span", style=lambda value: value and "text-decoration-line:underline" in value
        )
        return underline_span is not None

    def _is_class_quote(self, element: Tag) -> bool:
        quote_p = element.find("p", class_="Quote")
        return quote_p is not None


class CaselawSectionParser(LexParser):
    """Parser for caselaw sections."""

    def parse_content(self, soup: BeautifulSoup) -> list[CaselawSection]:
        """Parse the content of a BeautifulSoup object into a CaselawSection."""
        caselaw_parser = CaselawAndCaselawSectionsParser()
        metadata, sections = caselaw_parser.parse_content(soup)
        logger.debug(
            f"Parsed caselaw sections: {metadata.id}",
            extra={
                "doc_id": metadata.id,
                "doc_type": "caselaw",
                "court": metadata.court.value if metadata.court else None,
                "division": metadata.division,
                "doc_year": metadata.year,
                "doc_number": metadata.number,
                "processing_status": "success",
                "section_count": len(sections),
                "cite_as": metadata.cite_as,
            },
        )
        return sections


class CaselawParser(LexParser):
    """Parser for caselaw metadata."""

    def parse_content(self, soup: BeautifulSoup) -> Caselaw:
        """Parse the content of a BeautifulSoup object into a Caselaw."""
        caselaw_parser = CaselawAndCaselawSectionsParser()
        metadata, sections = caselaw_parser.parse_content(soup)
        logger.debug(
            f"Parsed caselaw: {metadata.id}",
            extra={
                "doc_id": metadata.id,
                "doc_type": "caselaw",
                "court": metadata.court.value if metadata.court else None,
                "division": metadata.division,
                "doc_year": metadata.year,
                "doc_number": metadata.number,
                "processing_status": "success",
                "cite_as": metadata.cite_as,
                "has_sections": len(sections) > 0,
            },
        )
        return metadata
