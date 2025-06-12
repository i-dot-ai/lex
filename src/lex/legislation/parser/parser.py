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

        legislation_with_content = self.parser.parse(soup)

        logger.debug(
            f"Parsed legislation: {legislation_with_content.id}",
            extra={
                "doc_id": legislation_with_content.id,
                "doc_type": legislation_with_content.type.value
                if legislation_with_content.type
                else None,
                "doc_year": legislation_with_content.year,
                "doc_number": legislation_with_content.number,
                "processing_status": "success",
                "has_xml": True,
                "title": legislation_with_content.title[:100]
                if legislation_with_content.title
                else None,
            },
        )

        legislation = Legislation(
            **legislation_with_content.model_dump(exclude={"sections", "schedules", "commentaries"})
        )

        return legislation


class LegislationSectionParser(LexParser):
    def __init__(self):
        self.parser = LegislationWithContentParser()

    def parse_content(self, soup: BeautifulSoup) -> list[LegislationSection]:
        legislation = self.parser.parse(soup)

        all_provisions = []
        all_provisions.extend(legislation.sections)
        all_provisions.extend(legislation.schedules)

        logger.debug(
            f"Parsed legislation sections: {legislation.id}",
            extra={
                "doc_id": legislation.id,
                "doc_type": legislation.type.value if legislation.type else None,
                "doc_year": legislation.year,
                "doc_number": legislation.number,
                "processing_status": "success",
                "has_xml": True,
                "section_count": len(legislation.sections),
                "schedule_count": len(legislation.schedules),
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

        all_provisions = [
            LegislationSection(**provision.model_dump()) for provision in all_provisions
        ]

        return all_provisions
