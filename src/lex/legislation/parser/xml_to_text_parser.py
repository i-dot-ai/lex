import re

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag


class SkipElement:
    """Sentinel class to indicate that an element should be completely skipped in parsing."""


class CLMLMarkdownParser:
    def __init__(self):
        self.skip_next_pnumber = False

    def parse_element(self, soup: BeautifulSoup, indent_level: int = 0, recurse_only: bool = False):
        # Check if the element is a known tag
        if not recurse_only:
            if tag_result := self._parse_known_tag(soup, indent_level):
                return tag_result

        result = ""

        # For element in elements
        for element in soup:
            # Skip whitespace-only text nodes
            if isinstance(element, NavigableString):
                string = self._parse_navigable_string(element)
                if string:
                    result += string

            # Only process Tag objects (elements with names)
            elif isinstance(element, Tag):
                # If it's a Pnumber, then add to text with a bracket afterwards, no newline
                if tag_result := self._parse_known_tag(element, indent_level):
                    if isinstance(tag_result, SkipElement):
                        continue  # skip the element entirely
                    result += tag_result
                else:
                    result += self._parse_unknown_tag(element, indent_level)

        result = self._regex_edits(result)

        return result

    def _parse_navigable_string(self, element: NavigableString) -> str:
        text_content = element.strip()

        if text_content:  # Only add non-empty text
            return text_content + " "
        return None

    def _parse_known_tag(self, element: Tag, indent_level: int) -> str:
        if element.name == "Pnumber":
            if self.skip_next_pnumber:
                self.skip_next_pnumber = False
                return SkipElement()
            return self._format_pnumber(element, indent_level)

        # If it's a BlockAmendment, handle Format attribute
        elif element.name == "BlockAmendment":
            return self._format_block_amendment(element, indent_level)

        elif element.name == "Text":
            return self.parse_element(element, indent_level, recurse_only=True)

        elif element.name == "Pblock":
            return self._format_pblock(element, indent_level)

        elif element.name == "P1group":
            return self._format_pgroup(element, indent_level)

        elif element.name == "Part":
            return self._format_part(element, indent_level)

        elif element.name == "Schedule":
            return self.parse_element(element, indent_level, recurse_only=True)

        elif element.name == "ScheduleBody":
            return self.parse_element(element, indent_level, recurse_only=True)

        # If it's a P\d+para, then recurse
        elif element.name and re.match(r"P\d+para$", element.name):
            return self.parse_element(element, indent_level, recurse_only=True)

        # If it's a P\d+group, then recurse
        elif element.name and re.match(r"P\d+group$", element.name):
            return self.parse_element(element, indent_level, recurse_only=True)

        # If it's any P\d+ element (like P2, P3, etc.), also recurse but calculate the new indent level.
        elif element.name and re.match(r"P\d+$", element.name):
            # Extract the paragraph level number (P1 -> 1, P2 -> 2, etc.)
            level = int(re.match(r"P(\d+)$", element.name).group(1))
            # Calculate intent: P1/P2 = 0, P3 = 1, P4 = 2, etc.
            new_indent = max(0, level - 2)
            return self.parse_element(element, new_indent, recurse_only=True)

        elif element.name == "UnorderedList":
            return self.parse_element(element, indent_level, recurse_only=True)

        elif element.name == "ListItem":
            return self._format_list_item(element, indent_level)

        elif element.name == "Para":
            return self.parse_element(element, indent_level, recurse_only=True)

        return None

    def _parse_unknown_tag(self, element: Tag, indent_level: int) -> str:
        # If it's anything else, add the text stripped with a newline
        return element.text.strip() + " "

    def _regex_edits(self, result: str) -> str:
        regex_edits = [
            (r"“ ", r"“"),  # note how this isn't a standard double quote character
            (r" ”", r"”"),
        ]

        for edit in regex_edits:
            result = re.sub(edit[0], edit[1], result)

        return result

    def _format_pnumber(self, element: BeautifulSoup, indent_level: int) -> str:
        indent = "\t" * indent_level
        return f"\n{indent}{element.text.strip()}) "

    def _format_block_amendment(self, element: BeautifulSoup, indent_level) -> str:
        # This implementation probably isn't perfect. It means that block amendments will always have at least the same indent level as the surrounding text.
        # We could probably make this more context aware.

        content = self.parse_element(element, indent_level + 1, recurse_only=True)
        indent = "\t" * indent_level

        return re.sub(r"\n", f"\n{indent}", content)

    def _format_pblock(self, element: BeautifulSoup, indent_level: int) -> str:
        result = ""
        starts_with = None

        # Check if Title is a direct child element
        for child in element.children:
            if isinstance(child, Tag) and child.name == "Title":
                starts_with = f"*{child.text.strip()}*\n"
            else:
                result += self.parse_element(child, indent_level)

        if starts_with:
            result = starts_with + result

        return result

    def _format_pgroup(self, element: BeautifulSoup, indent_level: int) -> str:
        result = ""
        starts_with = None

        # Check if Title is a direct child element
        for child in element.children:
            if isinstance(child, Tag) and child.name == "Title":
                group_title = child.text.strip()
                pnumber = element.find("Pnumber")
                if pnumber and "Article" not in pnumber.text:
                    starts_with = f"\n\nSection {pnumber.text.strip()}) **{group_title}**\n"
                    self.skip_next_pnumber = True
                elif pnumber and "Article" in pnumber.text:
                    starts_with = f"\n\n{pnumber.text.strip()}) **{group_title}**\n"
                    self.skip_next_pnumber = True

            else:
                result += self.parse_element(child, indent_level)

        if starts_with:
            result = starts_with + result

        return result

    def _format_part(self, element: BeautifulSoup, indent_level: int) -> str:
        result = ""
        starts_with = ""

        for child in element.children:
            if isinstance(child, Tag) and child.name == "Number":
                starts_with += f"## {child.text.strip()}\n"

            elif isinstance(child, Tag) and child.name == "Title":
                starts_with += f"## {child.text.strip()}\n"

            else:
                result += self.parse_element(child, indent_level)

        if starts_with:
            starts_with += "\n"
            result = starts_with + result

        return result

    def _format_list_item(self, element: BeautifulSoup, indent_level: int) -> str:
        indent = "\t" * (indent_level + 1)
        content = self.parse_element(element, indent_level + 1, recurse_only=True)
        return f"\n{indent}- {content.strip()}"
