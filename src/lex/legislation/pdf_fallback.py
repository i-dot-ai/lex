"""PDF fallback for legislation when XML is unavailable or empty.

This module provides functions to detect and process PDF-only legislation,
integrating with the existing LegislationPDFProcessor for OCR/extraction.
"""

import asyncio
import json
import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from lex.legislation.models import (
    Legislation,
    LegislationSection,
    LegislationType,
    ProvisionType,
)

logger = logging.getLogger(__name__)

# Minimum text length to consider XML content valid
MIN_VALID_TEXT_LENGTH = 100


def _extract_legislation_id_from_url(url: str) -> Optional[str]:
    """
    Extract legislation ID from a legislation.gov.uk URL.

    Args:
        url: URL like https://www.legislation.gov.uk/uksi/2025/123/data.xml

    Returns:
        ID like 'uksi/2025/123' or None if not parseable
    """
    # Remove scheme and domain
    match = re.search(r"legislation\.gov\.uk/([^/]+/[^/]+/[^/]+)", url)
    if match:
        return match.group(1)
    return None


def _extract_type_year_number(legislation_id: str) -> tuple[str, int, int]:
    """
    Extract type, year, and number from a legislation ID.

    Args:
        legislation_id: ID like 'uksi/2025/123'

    Returns:
        Tuple of (type, year, number)
    """
    parts = legislation_id.split("/")
    if len(parts) >= 3:
        leg_type = parts[0]
        year = int(parts[1])
        number = int(parts[2])
        return leg_type, year, number
    raise ValueError(f"Invalid legislation ID format: {legislation_id}")


async def get_pdf_url_from_resources(
    legislation_id: str,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    Get the PDF URL for a piece of legislation by checking the resources page.

    Args:
        legislation_id: ID like 'uksi/2025/123'
        timeout: HTTP timeout in seconds

    Returns:
        PDF URL or None if not available
    """
    resources_url = f"https://www.legislation.gov.uk/{legislation_id}/resources"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(resources_url, follow_redirects=True)

            if response.status_code != 200:
                logger.debug(f"Resources page not found for {legislation_id}")
                return None

            # Parse HTML to find PDF links
            soup = BeautifulSoup(response.text, "html.parser")

            # Look for PDF links - legislation.gov.uk uses various patterns
            pdf_links = soup.find_all("a", href=re.compile(r"\.pdf$", re.I))

            if pdf_links:
                # Prefer English versions
                for link in pdf_links:
                    href = link.get("href", "")
                    if "_en.pdf" in href.lower():
                        # Make absolute URL if relative
                        if href.startswith("/"):
                            return f"https://www.legislation.gov.uk{href}"
                        return href

                # Fall back to first PDF
                href = pdf_links[0].get("href", "")
                if href.startswith("/"):
                    return f"https://www.legislation.gov.uk{href}"
                return href

            logger.debug(f"No PDF found on resources page for {legislation_id}")
            return None

    except httpx.TimeoutException:
        logger.warning(f"Timeout checking resources for {legislation_id}")
        return None
    except Exception as e:
        logger.warning(f"Error checking resources for {legislation_id}: {e}")
        return None


async def check_pdf_available(legislation_id: str) -> bool:
    """
    Check if a PDF is available for a piece of legislation.

    Args:
        legislation_id: ID like 'uksi/2025/123'

    Returns:
        True if PDF is available
    """
    pdf_url = await get_pdf_url_from_resources(legislation_id)
    return pdf_url is not None


def _parse_extraction_result_to_legislation(
    extraction_json: str,
    legislation_id: str,
    pdf_url: str,
) -> tuple[Legislation, list[LegislationSection]]:
    """
    Convert PDF extraction JSON to Legislation and LegislationSection models.

    Args:
        extraction_json: JSON output from PDF processor
        legislation_id: ID like 'uksi/2025/123'
        pdf_url: Source PDF URL

    Returns:
        Tuple of (Legislation, list[LegislationSection])
    """
    data = json.loads(extraction_json)
    metadata = data.get("metadata", {})

    # Extract type, year, number from ID
    leg_type_str, year, number = _extract_type_year_number(legislation_id)

    # Try to parse the legislation type
    try:
        leg_type = LegislationType(leg_type_str)
    except ValueError:
        leg_type = LegislationType.UKPGA  # Default fallback

    # Parse date
    enactment_date = None
    date_str = metadata.get("date_enacted", "")
    if date_str:
        try:
            enactment_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Combine all text for the legislation
    preamble = data.get("preamble", "")
    sections = data.get("sections", [])
    schedules = data.get("schedules", [])

    all_text = preamble
    for section in sections:
        all_text += f"\n\n{section.get('heading', '')}\n{section.get('text', '')}"
    for schedule in schedules:
        all_text += f"\n\n{schedule.get('title', '')}\n{schedule.get('text', '')}"

    # Create Legislation model
    legislation = Legislation(
        id=f"http://www.legislation.gov.uk/id/{legislation_id}",
        uri=f"http://www.legislation.gov.uk/{legislation_id}",
        title=metadata.get("title", f"Unknown ({legislation_id})"),
        description=preamble[:500] if preamble else "",
        enactment_date=enactment_date,
        valid_date=None,
        modified_date=date.today(),
        publisher="legislation.gov.uk",
        category="secondary" if "si" in leg_type_str.lower() else "primary",
        type=leg_type,
        year=year,
        number=number,
        status="unknown",
        extent="",
        number_of_provisions=len(sections) + len(schedules),
        text=all_text.strip(),
        provenance_source=pdf_url,
        provenance_model="gpt-5-mini",
        provenance_prompt_version="pdf-extraction-1.0",
        provenance_timestamp=datetime.utcnow(),
        provenance_response_id="",
    )

    # Create LegislationSection models
    leg_sections = []
    legislation_uri = f"http://www.legislation.gov.uk/id/{legislation_id}"

    for i, section in enumerate(sections, 1):
        section_id = f"{legislation_uri}/section/{i}"
        leg_section = LegislationSection(
            id=section_id,
            uri=section_id,
            legislation_id=legislation_uri,
            title=section.get("heading", f"Section {section.get('number', i)}"),
            text=section.get("text", ""),
            extent="",
            provision_type=ProvisionType.SECTION,
        )
        leg_sections.append(leg_section)

    for i, schedule in enumerate(schedules, 1):
        schedule_id = f"{legislation_uri}/schedule/{i}"
        leg_section = LegislationSection(
            id=schedule_id,
            uri=schedule_id,
            legislation_id=legislation_uri,
            title=schedule.get("title", f"Schedule {schedule.get('number', i)}"),
            text=schedule.get("text", ""),
            extent="",
            provision_type=ProvisionType.SCHEDULE,
        )
        leg_sections.append(leg_section)

    return legislation, leg_sections


async def process_pdf_legislation(
    legislation_id: str,
    pdf_url: Optional[str] = None,
) -> tuple[Legislation, list[LegislationSection]] | None:
    """
    Process a PDF-only legislation item and return structured data.

    Args:
        legislation_id: ID like 'uksi/2025/123'
        pdf_url: Optional PDF URL (will be looked up if not provided)

    Returns:
        Tuple of (Legislation, list[LegislationSection]) or None if failed
    """
    from lex.processing.historical_pdf.processor import LegislationPDFProcessor

    # Get PDF URL if not provided
    if pdf_url is None:
        pdf_url = await get_pdf_url_from_resources(legislation_id)
        if pdf_url is None:
            logger.warning(f"No PDF available for {legislation_id}")
            return None

    logger.info(f"Processing PDF for {legislation_id}: {pdf_url}")

    try:
        # Extract type for processor
        leg_type_str, _, _ = _extract_type_year_number(legislation_id)

        # Process PDF
        processor = LegislationPDFProcessor()
        try:
            result = await processor.process_pdf(
                pdf_url=pdf_url,
                legislation_type=leg_type_str,
                identifier=legislation_id,
            )

            if not result.success:
                logger.warning(f"PDF processing failed for {legislation_id}: {result.error}")
                return None

            # Parse extraction result into models
            legislation, sections = _parse_extraction_result_to_legislation(
                extraction_json=result.extracted_data,
                legislation_id=legislation_id,
                pdf_url=pdf_url,
            )

            logger.info(
                f"PDF processed for {legislation_id}: "
                f"{len(sections)} sections, {len(legislation.text)} chars"
            )

            return legislation, sections

        finally:
            await processor.close()

    except Exception as e:
        logger.error(f"Error processing PDF for {legislation_id}: {e}", exc_info=True)
        return None


def is_xml_content_valid(text: str | None) -> bool:
    """
    Check if XML-extracted text content is valid (not empty or too short).

    Args:
        text: Extracted text content

    Returns:
        True if content is valid
    """
    if text is None:
        return False
    return len(text.strip()) >= MIN_VALID_TEXT_LENGTH


# Sync wrappers for use in non-async contexts


def get_pdf_url_sync(legislation_id: str) -> Optional[str]:
    """Synchronous wrapper for get_pdf_url_from_resources."""
    return asyncio.run(get_pdf_url_from_resources(legislation_id))


def check_pdf_available_sync(legislation_id: str) -> bool:
    """Synchronous wrapper for check_pdf_available."""
    return asyncio.run(check_pdf_available(legislation_id))


def process_pdf_legislation_sync(
    legislation_id: str,
    pdf_url: Optional[str] = None,
) -> tuple[Legislation, list[LegislationSection]] | None:
    """Synchronous wrapper for process_pdf_legislation."""
    return asyncio.run(process_pdf_legislation(legislation_id, pdf_url))
