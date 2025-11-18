"""
Fetch minimal metadata from legislation.gov.uk XML for PDF OCR enrichment.

Reuses existing XML parsing infrastructure.
"""

import io
import logging
from typing import Optional

from bs4 import BeautifulSoup
from pypdf import PdfReader

from lex.core.http import HttpClient
from lex.processing.historical_pdf.models import LegislationMetadata, PDFMetadata

logger = logging.getLogger(__name__)


def fetch_pdf_metadata(pdf_url: str) -> Optional[PDFMetadata]:
    """
    Fetch PDF file metadata (size, page count).

    Args:
        pdf_url: URL to PDF file

    Returns:
        PDFMetadata or None if fetch fails
    """
    try:
        http_client = HttpClient()

        # Download PDF to extract accurate page count
        response = http_client.get(pdf_url)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch PDF: {pdf_url} (status {response.status_code})")
            return None

        file_size = len(response.content)

        # Extract page count using pypdf
        page_count = None
        try:
            pdf_stream = io.BytesIO(response.content)
            pdf_reader = PdfReader(pdf_stream)
            page_count = len(pdf_reader.pages)
            logger.debug(f"PDF has {page_count} pages ({file_size / 1024:.0f}KB)")
        except Exception as e:
            logger.warning(f"Could not extract page count from PDF {pdf_url}: {e}")

        return PDFMetadata(
            file_size_bytes=file_size,
            page_count=page_count,
            pdf_url=pdf_url,
        )

    except Exception as e:
        logger.warning(f"Could not fetch PDF metadata for {pdf_url}: {e}")
        return None


def fetch_xml_metadata(legislation_type: str, identifier: str) -> Optional[LegislationMetadata]:
    """
    Fetch minimal XML metadata for PDF OCR prompt enrichment.

    This function reuses the existing HttpClient and BeautifulSoup parsing
    to extract only the metadata needed for OCR prompts.

    Args:
        legislation_type: e.g., 'ukpga', 'aep', 'ukla'
        identifier: e.g., 'Edw7/6/19', 'Geo3/41/90'

    Returns:
        LegislationMetadata or None if fetch fails
    """
    xml_url = f"http://www.legislation.gov.uk/{legislation_type}/{identifier}/enacted/data.xml"

    try:
        logger.debug(f"Fetching XML metadata from: {xml_url}")

        http_client = HttpClient()
        response = http_client.get(xml_url)

        if response.status_code != 200:
            logger.warning(
                f"Failed to fetch XML metadata: {xml_url} (status {response.status_code})"
            )
            return None

        # Parse XML (same approach as existing xml_parser.py)
        soup = BeautifulSoup(response.text, "xml")

        # Extract minimal metadata (only what's needed for OCR prompt)
        title = None
        if soup.find("dc:title"):
            title = soup.find("dc:title").get_text(strip=True)

        year = None
        if soup.find("ukm:Year"):
            year = soup.find("ukm:Year").get("Value")

        number = None
        if soup.find("ukm:Number"):
            number = soup.find("ukm:Number").get("Value")

        enactment_date = None
        if soup.find("ukm:EnactmentDate"):
            enactment_date = soup.find("ukm:EnactmentDate").get("Date")

        # Extract PDF URL from XML
        pdf_url = None
        for alternative in soup.find_all("ukm:Alternative"):
            if alternative.get("URI") and alternative.get("URI").endswith(".pdf"):
                pdf_url = alternative.get("URI")
                break

        # Fetch PDF metadata if URL available
        pdf_metadata = None
        if pdf_url:
            pdf_metadata = fetch_pdf_metadata(pdf_url)

        metadata = LegislationMetadata(
            title=title,
            year=year,
            number=number,
            enactment_date=enactment_date,
            type=legislation_type,
            pdf=pdf_metadata,
        )

        logger.info(
            f"Fetched metadata for {legislation_type}/{identifier}: {metadata.title} "
            f"(PDF: {pdf_metadata.file_size_bytes / 1024:.0f}KB)"
            if pdf_metadata and pdf_metadata.file_size_bytes
            else ""
        )
        return metadata

    except Exception as e:
        logger.warning(f"Could not fetch XML metadata for {legislation_type}/{identifier}: {e}")
        return None
