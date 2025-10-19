import logging

from bs4 import BeautifulSoup

from lex.core.exceptions import ProcessedException
from lex.core.http import HttpClient
from lex.legislation.models import Legislation, LegislationSection
from lex.legislation.parser.xml_parser import LegislationParser as LegislationWithContentParser

logger = logging.getLogger(__name__)
http_client = HttpClient()


def construct_pdf_url(legislation_id: str) -> str:
    """
    Extract PDF URL from legislation XML metadata.

    Args:
        legislation_id: Format like http://www.legislation.gov.uk/id/ukpga/Geo3/41/90

    Returns:
        PDF URL extracted from XML metadata atom:link element, or None if not found
    """
    try:
        # Convert ID URL to data.xml URL
        # http://www.legislation.gov.uk/id/ukpga/Geo5/6-7/38
        # -> http://www.legislation.gov.uk/ukpga/Geo5/6-7/38/data.xml
        data_url = legislation_id.replace("/id/", "/") + "/data.xml"

        # Fetch XML metadata
        response = http_client.get(data_url)
        response.raise_for_status()

        # Parse XML to find PDF URL
        soup = BeautifulSoup(response.content, "xml")

        # Look for atom:link with type="application/pdf" and title="Original PDF"
        # <atom:link rel="alternate" href="http://www.legislation.gov.uk/ukpga/Geo5/6-7/38/pdfs/ukpga_19160038_en.pdf"
        #            type="application/pdf" title="Original PDF"/>
        pdf_link = soup.find("atom:link", attrs={"type": "application/pdf", "title": "Original PDF"})

        if pdf_link and pdf_link.get("href"):
            pdf_url = pdf_link.get("href")
            logger.debug(f"Extracted PDF URL from XML metadata: {pdf_url}")
            return pdf_url
        else:
            logger.warning(f"No PDF URL found in XML metadata for {legislation_id}")
            return None

    except Exception as e:
        logger.error(f"Error fetching PDF URL from XML metadata for {legislation_id}: {e}")
        return None


def check_pdf_exists(pdf_url: str) -> bool:
    """Check if PDF exists at given URL using HEAD request."""
    try:
        response = http_client.head(pdf_url)
        return response.status_code == 200
    except Exception as e:
        logger.debug(f"Error checking PDF URL {pdf_url}: {e}")
        return False


class LegislationParser:
    def __init__(self):
        self.parser = LegislationWithContentParser()

    def parse_content(self, soup: BeautifulSoup) -> Legislation:
        """Wrapper function to take the Lex Graph parser and return the Legislation object"""

        try:
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

        except ProcessedException as e:
            # Extract metadata from XML even if body is empty
            legislation_element = soup.find("Legislation")
            legislation_id = legislation_element.get("IdURI") if legislation_element else None

            if legislation_id:
                # Construct potential PDF URL
                pdf_url = construct_pdf_url(legislation_id)

                # Log PDF-only legislation for future processing
                logger.warning(
                    f"PDF-only legislation detected: {legislation_id}",
                    extra={
                        "doc_id": legislation_id,
                        "processing_status": "pdf_only",
                        "pdf_url": pdf_url,
                        "has_xml": False,
                        "title": soup.find("dc:title").text if soup.find("dc:title") else None,
                    },
                )

            # Re-raise to skip this document
            raise e


class LegislationSectionParser:
    def __init__(self):
        self.parser = LegislationWithContentParser()

    def parse_content(self, soup: BeautifulSoup) -> list[LegislationSection]:
        try:
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

        except ProcessedException as e:
            # Extract metadata from XML even if body is empty
            legislation_element = soup.find("Legislation")
            legislation_id = legislation_element.get("IdURI") if legislation_element else None

            if legislation_id:
                # Construct potential PDF URL
                pdf_url = construct_pdf_url(legislation_id)

                # Log PDF-only legislation for future processing
                logger.warning(
                    f"PDF-only legislation detected (sections): {legislation_id}",
                    extra={
                        "doc_id": legislation_id,
                        "processing_status": "pdf_only",
                        "pdf_url": pdf_url,
                        "has_xml": False,
                        "title": soup.find("dc:title").text if soup.find("dc:title") else None,
                    },
                )

            # Re-raise to skip this document
            raise e
