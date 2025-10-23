import logging

from bs4 import BeautifulSoup

from lex.core.parser import LexParser
from lex.legislation.models import Legislation, LegislationSection
from lex.legislation.parser.xml_parser import LegislationParser as LegislationWithContentParser

logger = logging.getLogger(__name__)


class LegislationParser(LexParser):
    def __init__(self):
        self.parser = LegislationWithContentParser()

    def parse_content(self, soup: BeautifulSoup) -> Legislation:
        """Wrapper function to take the Lex Graph parser and return the Legislation object"""

        legislation, sections, schedules = self.parser.parse(soup)

        logger.debug(
            f"Parsed legislation: {legislation.id}",
            extra={
                "doc_id": legislation.id,
                "doc_type": legislation.type.value if legislation.type else None,
                "doc_year": legislation.year,
                "doc_number": legislation.number,
                "processing_status": "success",
                "has_xml": True,
                "title": legislation.title[:100] if legislation.title else None,
            },
        )

        return legislation


class LegislationSectionParser(LexParser):
    def __init__(self):
        self.parser = LegislationWithContentParser()

    def parse_content(self, soup: BeautifulSoup) -> list[LegislationSection]:
        legislation, sections, schedules = self.parser.parse(soup)

        all_provisions: list[LegislationSection] = []
        all_provisions.extend(sections)
        all_provisions.extend(schedules)

        logger.debug(
            f"Parsed legislation sections: {legislation.id}",
            extra={
                "doc_id": legislation.id,
                "doc_type": legislation.type.value if legislation.type else None,
                "doc_year": legislation.year,
                "doc_number": legislation.number,
                "processing_status": "success",
                "has_xml": True,
                "section_count": len(sections),
                "schedule_count": len(schedules),
                "provision_count": len(all_provisions),
                "title": legislation.title[:100] if legislation.title else None,
            },
        )

        # Warn if no provisions found
        if len(all_provisions) == 0:
            logger.warning(
                f"No sections or schedules found in legislation: {legislation.id}",
                extra={
                    "doc_id": legislation.id,
                    "doc_type": legislation.type.value if legislation.type else None,
                    "doc_year": legislation.year,
                    "processing_status": "no_provisions",
                },
            )

        return all_provisions
