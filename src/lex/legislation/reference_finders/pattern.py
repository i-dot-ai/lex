import re
from dataclasses import dataclass
from typing import List, Tuple, Union

from lex.legislation.models import FreeTextReference

from .base import ReferenceFinder


@dataclass
class UKReferencePatterns:
    """Contains regex patterns for parsing UK legislative references."""

    # Common patterns
    _SECTION = r"section"
    _SECTIONS = rf"{_SECTION}s?"
    _NUMBER = r"(\d+)(?:\([^)]*\))?"
    _NUMBER_LIST = r"(\d+(?:\s*,\s*\d+)*(?:\s*,?\s+(?:and|or)\s+\d+)?)"
    _NUMBER_RANGE = rf"{_NUMBER}\s+to\s+{_NUMBER}"

    # UK Act patterns
    _ACT = r"[A-Z][a-zA-Z\s\'-]+?Act\s+\d{4}"
    _OPTIONAL_PART = r"(?:Part\s+\d+\s+of\s+)?"
    _ACT_WITH_PART = rf"{_OPTIONAL_PART}(?:the\s+)?({_ACT})"

    # Section patterns
    SECTION_RANGE = rf"{_SECTIONS}\s+{_NUMBER_RANGE}"
    SECTION_MULTIPLE = rf"{_SECTIONS}\s+{_NUMBER_LIST}"
    SECTION_SINGLE = rf"{_SECTION}\s+{_NUMBER}"

    # Act patterns
    ACT_ONLY = rf"(?:^|[^.a-z]){_ACT_WITH_PART}\s*(?:\([^)]*\))?(?!\s+{_SECTION})"

    # Combined patterns
    _OF_ACT = rf"of\s+the\s+([^.]+?Act\s+\d{4})"
    ACT_SECTION_RANGE = rf"{_SECTIONS}\s+{_NUMBER_RANGE}\s+{_OF_ACT}"
    ACT_SECTION_MULTIPLE = rf"{_SECTIONS}\s+{_NUMBER_LIST}\s+{_OF_ACT}"
    ACT_SECTION_SINGLE = rf"{_SECTION}\s+{_NUMBER}\s+{_OF_ACT}"


@dataclass
class EUReferencePatterns:
    """Contains regex patterns for parsing EU legislative references."""

    # Common patterns
    _ARTICLE = r"[Aa]rticle"
    _ARTICLES = rf"{_ARTICLE}s?"
    _NUMBER = r"(\d+)(?:\([^)]*\))?"
    _NUMBER_LIST = r"(\d+(?:\s*,\s*\d+)*(?:\s*,?\s+(?:and|or)\s+\d+)?)"
    _NUMBER_RANGE = rf"{_NUMBER}\s+to\s+{_NUMBER}"

    # EU legislation patterns
    _EU_TYPE = r"(?:EC|EU|EEC)"
    _LEG_TYPE = r"(?:Regulation|Directive|Decision|Treaty)"
    _FORMAL_CITATION = (
        rf"{_LEG_TYPE}\s+(?:\(?{_EU_TYPE}\)?\s+)?(?:19|20\d{2}/\d+|(?:\d+/)+{_EU_TYPE})"
    )
    _INFORMAL_CITATION = rf"[A-Z][a-zA-Z\s]+?(?:{_LEG_TYPE})"
    _ACT = rf"(?:{_FORMAL_CITATION}|{_INFORMAL_CITATION})"

    # Article (section) patterns
    SECTION_RANGE = rf"{_ARTICLES}\s+{_NUMBER_RANGE}"
    SECTION_MULTIPLE = rf"{_ARTICLES}\s+{_NUMBER_LIST}"
    SECTION_SINGLE = rf"{_ARTICLE}\s+{_NUMBER}"

    # Act patterns
    ACT_ONLY = rf"(?:^|[^.a-z])(?:the\s+)?{_ACT}(?!\s+{_ARTICLE})"

    # Combined patterns
    _OF_ACT = rf"of\s+(?:the\s+)?{_ACT}"
    ACT_SECTION_RANGE = rf"{_ARTICLES}\s+{_NUMBER_RANGE}\s+{_OF_ACT}"
    ACT_SECTION_MULTIPLE = rf"{_ARTICLES}\s+{_NUMBER_LIST}\s+{_OF_ACT}"
    ACT_SECTION_SINGLE = rf"{_ARTICLE}\s+{_NUMBER}\s+{_OF_ACT}"
    ACT_PART = rf"Part\s+\d+\s+of\s+{_ACT}"


class PatternReferenceFinder(ReferenceFinder):
    """Implementation of pattern based ReferenceFinder for parsing legislative references."""

    def __init__(self, patterns: Union[UKReferencePatterns, EUReferencePatterns]):
        self.patterns = patterns

    def _clean_section_number(self, section: str) -> str:
        """Extract just the main section number from a section reference.

        For example:
        - "115(2)" becomes "115"
        - "21(1)" becomes "21"
        - "45" remains "45"
        """
        if not section:
            return section

        # If there's a parenthesis, extract just the main section number
        if "(" in section:
            return section.split("(")[0]
        return section

    def find_references(self, source_id: str, text: str) -> List[FreeTextReference]:
        """Find all references in the given text."""

        assert source_id, "source_id must be provided"
        assert source_id != "", "source_id must not be empty"

        if not text or text.strip() == "":
            return []

        # Use sets to track unique references
        section_refs = set()  # For standalone sections
        act_section_refs = set()  # For act-section pairs
        act_refs = set()  # For standalone acts

        # First pass: Explicit act-section combinations
        act_section_pairs = self._extract_acts_with_sections(text)
        for act, section in act_section_pairs:
            act = act.strip()
            if isinstance(section, list):
                for sec in section:
                    clean_section = self._clean_section_number(str(sec))
                    act_section_refs.add(
                        FreeTextReference(
                            source_id=source_id,
                            act=act,
                            section=clean_section,
                            context=text,
                        )
                    )
            else:
                clean_section = self._clean_section_number(str(section))
                act_section_refs.add(
                    FreeTextReference(
                        source_id=source_id,
                        act=act,
                        section=clean_section,
                        context=text,
                    )
                )

        # Second pass: Handle standalone sections
        standalone_sections = self._extract_sections(text)
        for section in standalone_sections:
            if isinstance(section, list):
                for sec in section:
                    sec_str = self._clean_section_number(str(sec))
                    # Only add if not already part of an act-section reference
                    if not any(ref.section == sec_str and ref.act for ref in act_section_refs):
                        section_refs.add(
                            FreeTextReference(source_id=source_id, section=sec_str, context=text)
                        )
            else:
                sec_str = self._clean_section_number(str(section))
                # Only add if not already part of an act-section reference
                if not any(ref.section == sec_str and ref.act for ref in act_section_refs):
                    section_refs.add(
                        FreeTextReference(source_id=source_id, section=sec_str, context=text)
                    )

        # Third pass: Handle standalone acts (only if no other references found)
        if not (section_refs or act_section_refs):
            standalone_acts = self._extract_acts(source_id, text)
            act_refs.update(standalone_acts)

        # Combine all unique references
        all_refs = act_section_refs | section_refs | act_refs

        return sorted(list(all_refs), key=lambda x: (x.act or "", x.section or ""))

    def _clean_act_name(self, act_name: str) -> str:
        """Clean up act name by removing prefixes like 'of the', 'of', 'the'."""
        act_name = act_name.strip()

        if len(act_name) > 80:
            # it is unlikely that an act name is longer than 80 characters
            # this is usually when it has matched with other capitalised words in a longer sentence
            # therefore we need to try to isolate the act name
            pattern = r"((?:(?:[A-Z][a-z]*|and|of|the|by)\s+)+Act\s+\d{4})"
            match = re.search(pattern, act_name)
            if match:
                act_name = match.group(1)

        # Remove common prefixes
        prefixes = [
            "and ",
            "of the ",
            "of ",
            "the ",
            "in the",
            "to the ",
            "within the meaning of the ",
            "references to the ",
            "Act or the ",
            "Act or ",
            "Scheduled Estimates in the ",
            "Amendment to the ",
            "Scheduled Estimates in the ",
            "Scheduled Estimate in the ",
            "Schedule to ",
            "Schedule to the ",
            "Amendment to the ",
            "Amendments to the ",
            "Amendments of ",
            "Amendment of ",
            "This paragraph amends the ",
            "Until the ",
            "Repeal of ",
        ]
        for prefix in prefixes:
            if act_name.lower().startswith(prefix.lower()):
                act_name = act_name[len(prefix) :].strip()

        # Split on common phrases before an Act is referenced
        prefix_splitters = [
            "of the ",
            "under the ",
            "as in the ",
            "means the",
            " under ",
        ]
        for prefix in prefix_splitters:
            if prefix in act_name:
                act_name = act_name.split(prefix)[1]
                break

        # Remove any 1-2 letter prefixes followed by the
        # example cases:
        # - "za the Caravan Sites and Control of Development Act 1960"
        # - "b the Housing Act 1985"
        # - "a the Mobile Homes Act 1983"
        if re.match(r"^[a-zA-Z]{1,2}\s+(?:to\s+)?the\s+", act_name):
            act_name = re.sub(r"^[a-zA-Z]{1,2}\s+(?:to\s+)?the\s+", "", act_name)

        # Trim to the first capital letter that appears
        act_name = re.sub(r"^[^A-Z]*", "", act_name)

        # Re-run the prefixes removal on any capitalised prefixes
        for prefix in prefixes:
            if prefix[0].isupper() and act_name.startswith(prefix):
                act_name = act_name[len(prefix) :].strip()

        return act_name.strip()

    def _extract_sections(self, text: str) -> List[Union[int, List[int], str]]:
        """Extract all section numbers from the text."""
        sections = []

        # Process section ranges
        for match in re.finditer(self.patterns.SECTION_RANGE, text, re.IGNORECASE):
            start, end = int(match.group(1)), int(match.group(2))
            sections.append(list(range(start, end + 1)))

        # Process multiple sections
        for match in re.finditer(self.patterns.SECTION_MULTIPLE, text, re.IGNORECASE):
            section_str = match.group(1)
            if "to" not in section_str:  # Skip ranges (already handled above)
                nums = [int(num) for num in re.findall(r"\d+", section_str)]
                if len(nums) > 1:
                    sections.append(nums)
                elif len(nums) == 1 and not any(
                    isinstance(s, list) and nums[0] in s for s in sections
                ):
                    sections.append(nums[0])

        # Process single sections
        for match in re.finditer(self.patterns.SECTION_SINGLE, text, re.IGNORECASE):
            section_num = match.group(1)
            if "(" in section_num:
                section_num = int(self._clean_section_number(section_num))
            else:
                section_num = int(section_num)

            if not any(isinstance(s, list) and section_num in s for s in sections):
                sections.append(section_num)

        return sections

    def _extract_acts(self, source_id: str, text: str) -> List[FreeTextReference]:
        """Extract standalone act references."""
        references = []
        for match in re.finditer(self.patterns.ACT_ONLY, text, re.IGNORECASE):
            if match.lastindex is None or not match.group(1):
                continue

            act_name = self._clean_act_name(match.group(1))
            if "may be cited as the" in act_name:
                continue  # don't include self-citation cases

            if act_name is not None and act_name != "":
                references.append(
                    FreeTextReference(source_id=source_id, act=act_name, context=text)
                )
        return references

    def _extract_acts_with_sections(self, text: str) -> List[Tuple[str, Union[str, List[int]]]]:
        """Extract combined act and section references."""
        # Use a set to track unique (act, section) pairs
        result_set = set()

        # Process section ranges within acts (explicit)
        for match in re.finditer(self.patterns.ACT_SECTION_RANGE, text, re.IGNORECASE):
            if (match.lastindex is not None) and (
                match.group(1) and match.lastindex >= 3 and match.group(3)
            ):
                start, end = int(match.group(1)), int(match.group(2))
                act_name = self._clean_act_name(match.group(3))
                result_set.add((act_name, tuple(range(start, end + 1))))

        # Process multiple sections within acts (explicit)
        for match in re.finditer(self.patterns.ACT_SECTION_MULTIPLE, text, re.IGNORECASE):
            if (match.lastindex is not None) and (
                match.group(1) and match.lastindex >= 2 and match.group(2)
            ):
                section_str, act_name = (
                    match.group(1),
                    self._clean_act_name(match.group(2)),
                )

                if "to" not in section_str:
                    nums = [int(num) for num in re.findall(r"\d+", section_str)]
                    if len(nums) > 1:
                        result_set.add((act_name, tuple(nums)))

        # Process single sections within acts (explicit)
        for match in re.finditer(self.patterns.ACT_SECTION_SINGLE, text, re.IGNORECASE):
            if (match.lastindex is not None) and (
                match.group(1) and match.lastindex >= 2 and match.group(2)
            ):
                section_num, act_name = (
                    match.group(1),
                    self._clean_act_name(match.group(2)),
                )
                result_set.add((act_name, section_num))

        # Handle 'of that Act' references
        that_act_pattern = re.compile(
            r"section\s+(\d+(?:\(\d+\))?)\s+of\s+that\s+Act", re.IGNORECASE
        )
        act_pattern = re.compile(r"([A-Z][a-zA-Z\s\'-]+?Act\s+\d{4})", re.IGNORECASE)

        act_matches = list(act_pattern.finditer(text))
        that_act_matches = list(that_act_pattern.finditer(text))

        if act_matches and that_act_matches:
            # Find the most recent act before each "that Act" reference
            for that_match in that_act_matches:
                that_pos = that_match.start()
                section_num = that_match.group(1)

                # Find the nearest preceding act
                nearest_act = None
                nearest_distance = float("inf")

                for act_match in act_matches:
                    act_pos = act_match.end()
                    if act_pos < that_pos and that_pos - act_pos < nearest_distance:
                        nearest_distance = that_pos - act_pos
                        nearest_act = self._clean_act_name(act_match.group(1))

                if nearest_act:
                    result_set.add((nearest_act, section_num))

        # These patterns can overlap, so using separate regex patterns for different forms
        # to avoid duplicating references

        # Handle forms like "section X of the Act Y"
        section_of_the_act_pattern = re.compile(
            r"(?:^|[^a-zA-Z])(?:section|sections)\s+(\d+(?:\([^)]*\))?)\s+of\s+the\s+([A-Z][a-zA-Z\s\'-]+?Act\s+\d{4})",
            re.IGNORECASE,
        )
        for match in section_of_the_act_pattern.finditer(text):
            section_num = match.group(1)
            act_name = self._clean_act_name(match.group(2))
            result_set.add((act_name, section_num))

        # Handle "section X of Y Act 1234" (without "the")
        section_of_act_pattern = re.compile(
            r"(?:^|[^a-zA-Z])(?:section|sections)\s+(\d+(?:\([^)]*\))?)\s+of\s+(?!the\s+)([A-Z][a-zA-Z\s\'-]+?Act\s+\d{4})",
            re.IGNORECASE,
        )
        for match in section_of_act_pattern.finditer(text):
            section_num = match.group(1)
            act_name = self._clean_act_name(match.group(2))
            result_set.add((act_name, section_num))

        # Handle forms like "under section X of the Act Y"
        under_section_pattern = re.compile(
            r"under\s+section\s+(\d+(?:\([^)]*\))?)\s+of\s+(?:the\s+)?([A-Z][a-zA-Z\s\'-]+?Act\s+\d{4})",
            re.IGNORECASE,
        )
        for match in under_section_pattern.finditer(text):
            section_num = match.group(1)
            act_name = self._clean_act_name(match.group(2))
            result_set.add((act_name, section_num))

        # Convert set of tuples back to list, converting tuple ranges back to lists
        results = []
        for act, section in result_set:
            if isinstance(section, tuple):
                results.append((act, list(section)))
            else:
                results.append((act, section))

        return results
