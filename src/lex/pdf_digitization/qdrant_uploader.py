"""
Simple uploader to merge XML metadata with PDF extractions and upload to Qdrant.
"""

import json
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from qdrant_client.models import PointStruct

from lex.core.embeddings import generate_dense_embedding, generate_sparse_embedding
from lex.core.http import HttpClient
from lex.core.qdrant_client import get_qdrant_client
from lex.legislation.models import (
    Legislation,
    LegislationCategory,
    LegislationSection,
    LegislationType,
    ProvisionType,
)

logger = logging.getLogger(__name__)
http_client = HttpClient()

# Map XML DocumentMainType to LegislationType enum
DOCUMENT_TYPE_MAP = {
    "UnitedKingdomPublicGeneralAct": LegislationType.UKPGA,
    "UnitedKingdomLocalAct": LegislationType.UKLA,
    "UnitedKingdomPrivateOrPersonalAct": LegislationType.UKPPA,
    "GreatBritainLocalAct": LegislationType.GBLA,
    "EnglandAct": LegislationType.AEP,
    "NorthernIrelandStatutoryRuleOrOrder": LegislationType.NISRO,
    "NorthernIrelandOrderInCouncil": LegislationType.NISI,
    "UnitedKingdomStatutoryRuleOrOrder": LegislationType.UKSRO,
    # Add more mappings as needed
}

# Map legislation type string to enum (all 28 types)
LEGTYPE_STRING_MAP = {
    "ukpga": LegislationType.UKPGA,
    "asp": LegislationType.ASP,
    "asc": LegislationType.ASC,
    "anaw": LegislationType.ANAW,
    "wsi": LegislationType.WSI,
    "uksi": LegislationType.UKSI,
    "ssi": LegislationType.SSI,
    "ukcm": LegislationType.UKCM,
    "nisr": LegislationType.NISR,
    "nia": LegislationType.NIA,
    "eudn": LegislationType.EUDN,
    "eudr": LegislationType.EUDR,
    "eur": LegislationType.EUR,
    "ukla": LegislationType.UKLA,
    "ukppa": LegislationType.UKPPA,
    "apni": LegislationType.APNI,
    "gbla": LegislationType.GBLA,
    "aosp": LegislationType.AOSP,
    "aep": LegislationType.AEP,
    "apgb": LegislationType.APGB,
    "mwa": LegislationType.MWA,
    "aip": LegislationType.AIP,
    "mnia": LegislationType.MNIA,
    "nisro": LegislationType.NISRO,
    "nisi": LegislationType.NISI,
    "uksro": LegislationType.UKSRO,
    "ukmo": LegislationType.UKMO,
    "ukci": LegislationType.UKCI,
}


def fetch_xml_metadata(legislation_id: str) -> dict[str, Any]:
    """
    Fetch XML metadata for a legislation document.

    Args:
        legislation_id: Format like "ukla/Vict/14-15/51"

    Returns:
        Dictionary with extracted XML fields
    """
    # Convert ID to data.xml URL
    data_url = f"http://www.legislation.gov.uk/{legislation_id}/data.xml"

    try:
        response = http_client.get(data_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "xml")

        # Extract Dublin Core metadata
        dc_identifier = soup.find("dc:identifier")
        dc_title = soup.find("dc:title")
        dc_description = soup.find("dc:description")
        dc_publisher = soup.find("dc:publisher")

        # Extract UKM metadata
        doc_classification = soup.find("ukm:DocumentClassification")
        category = doc_classification.find("ukm:DocumentCategory") if doc_classification else None
        main_type = doc_classification.find("ukm:DocumentMainType") if doc_classification else None
        status = doc_classification.find("ukm:DocumentStatus") if doc_classification else None

        primary_meta = soup.find("ukm:PrimaryMetadata")
        year = primary_meta.find("ukm:Year") if primary_meta else None
        number = primary_meta.find("ukm:Number") if primary_meta else None
        enactment_date = primary_meta.find("ukm:EnactmentDate") if primary_meta else None

        return {
            "id": dc_identifier.text if dc_identifier else None,
            "title": dc_title.text if dc_title else None,
            "description": dc_description.text if dc_description else None,
            "publisher": dc_publisher.text if dc_publisher else None,
            "category": category.get("Value") if category else None,
            "main_type": main_type.get("Value") if main_type else None,
            "status": status.get("Value") if status else None,
            "year": int(year.get("Value")) if year else None,
            "number": int(number.get("Value")) if number else None,
            "enactment_date": enactment_date.get("Date") if enactment_date else None,
        }
    except Exception as e:
        logger.error(f"Failed to fetch XML metadata for {legislation_id}: {e}")
        return {}


def merge_xml_and_pdf(xml_meta: dict[str, Any], pdf_result: dict[str, Any]) -> Legislation:
    """
    Merge XML metadata with PDF extraction to create Legislation record.

    Args:
        xml_meta: Dictionary from fetch_xml_metadata()
        pdf_result: PDF extraction result from JSONL

    Returns:
        Legislation model instance
    """
    import re

    # Parse extracted_data if it's a string
    extracted_data = pdf_result.get("extracted_data", {})
    if isinstance(extracted_data, str):
        extracted_data = json.loads(extracted_data)

    extracted = extracted_data
    pdf_meta = extracted.get("metadata", {})

    # Map document type from XML, fallback to PDF result
    main_type = xml_meta.get("main_type")
    leg_type = DOCUMENT_TYPE_MAP.get(main_type) if main_type else None

    if not leg_type:
        # Fallback: Use legislation_type from PDF result
        leg_type_str = pdf_result.get("legislation_type", "").lower()
        leg_type = LEGTYPE_STRING_MAP.get(leg_type_str)

    # Derive category from XML or infer from type
    xml_category = xml_meta.get("category")
    if xml_category == "primary":
        category = LegislationCategory.PRIMARY
    elif xml_category == "secondary":
        category = LegislationCategory.SECONDARY
    elif xml_category == "european":
        category = LegislationCategory.EUROPEAN
    elif xml_category == "euretained":
        category = LegislationCategory.EUROPEAN_RETAINED
    elif leg_type in [
        # Secondary legislation types
        LegislationType.NISRO,
        LegislationType.UKSI,
        LegislationType.NISR,
        LegislationType.UKSRO,
        LegislationType.WSI,
        LegislationType.SSI,
        LegislationType.NISI,
        LegislationType.UKMO,
        LegislationType.UKCI,
        LegislationType.UKCM,
        LegislationType.MWA,
        LegislationType.MNIA,
    ]:
        category = LegislationCategory.SECONDARY
    elif leg_type in [LegislationType.EUR, LegislationType.EUDR, LegislationType.EUDN]:
        category = LegislationCategory.EUROPEAN
    else:
        # Primary legislation types (Acts)
        category = LegislationCategory.PRIMARY

    # Use XML description if available, else PDF preamble
    description = xml_meta.get("description") or extracted.get("preamble", "")
    if not xml_meta.get("description") and len(description) > 500:
        # Truncate preamble if used as description
        description = description[:497] + "..."

    # Use XML enactment date if available, else PDF date
    enact_date = xml_meta.get("enactment_date") or pdf_meta.get("date_enacted")
    if enact_date and isinstance(enact_date, str):
        enact_date = date.fromisoformat(enact_date)

    # Get URI (remove /enacted suffix if present)
    legislation_id = xml_meta.get("id", "")
    uri = legislation_id.replace("/enacted", "")

    # Count provisions from PDF
    sections = extracted.get("sections", [])
    schedules = extracted.get("schedules", [])
    num_provisions = len(sections) + len(schedules)

    # Extract provenance from PDF result
    provenance = pdf_result.get("provenance", {})

    # Extract year and number from identifier if not in XML
    year = xml_meta.get("year")
    number = xml_meta.get("number")

    if not year or not number:
        # Try to extract from identifier (e.g., "1922/1" or "Vict/14-15/51")
        identifier = pdf_result.get("identifier", "")
        parts = identifier.split("/")

        # Try first part as year
        if parts and re.match(r"^\d{4}$", parts[0]):
            year = int(parts[0]) if not year else year
            if len(parts) > 1 and parts[1].isdigit():
                number = int(parts[1]) if not number else number

        # Default fallbacks if still missing
        if not year:
            year = 1900  # Default fallback year
        if not number:
            number = 1  # Default fallback number

    return Legislation(
        id=legislation_id,
        uri=uri,
        title=xml_meta.get("title", ""),
        description=description,
        enactment_date=enact_date,
        publisher=xml_meta.get("publisher", "The National Archives"),
        category=category,
        type=leg_type,
        year=year,
        number=number,
        status=xml_meta.get("status", "revised"),
        extent=[],  # Not available in XML or PDF
        number_of_provisions=num_provisions,
        # Provenance tracking
        provenance_source="llm_ocr",
        provenance_model=provenance.get("model"),
        provenance_prompt_version=provenance.get("prompt_version"),
        provenance_timestamp=provenance.get("timestamp"),
        provenance_response_id=provenance.get("response_id"),
    )


def create_section_records(
    legislation: Legislation, pdf_result: dict[str, Any]
) -> list[LegislationSection]:
    """
    Create LegislationSection records from PDF extraction.

    Args:
        legislation: Parent Legislation record
        pdf_result: PDF extraction result from JSONL

    Returns:
        List of LegislationSection instances
    """
    # Parse extracted_data if it's a string
    extracted_data = pdf_result.get("extracted_data", {})
    if isinstance(extracted_data, str):
        extracted_data = json.loads(extracted_data)

    extracted = extracted_data
    sections = extracted.get("sections", [])
    schedules = extracted.get("schedules", [])

    # Extract provenance from PDF result
    provenance = pdf_result.get("provenance", {})

    section_records = []

    # Process regular sections
    for section in sections:
        section_num = section.get("number", "")
        section_id = f"{legislation.id}/section/{section_num}"
        section_uri = section_id.replace("/enacted", "")

        section_records.append(
            LegislationSection(
                id=section_id,
                uri=section_uri,
                legislation_id=legislation.id,
                title=section.get("heading") or "",  # heading -> title, handle None
                text=section.get("text", ""),
                extent=[],  # Not available
                provision_type=ProvisionType.SECTION,
                # Provenance tracking
                provenance_source="llm_ocr",
                provenance_model=provenance.get("model"),
                provenance_prompt_version=provenance.get("prompt_version"),
                provenance_timestamp=provenance.get("timestamp"),
                provenance_response_id=provenance.get("response_id"),
            )
        )

    # Process schedules
    for schedule in schedules:
        schedule_num = schedule.get("number", "")
        schedule_id = f"{legislation.id}/schedule/{schedule_num}"
        schedule_uri = schedule_id.replace("/enacted", "")

        section_records.append(
            LegislationSection(
                id=schedule_id,
                uri=schedule_uri,
                legislation_id=legislation.id,
                title=schedule.get("title") or "",  # Handle None
                text=schedule.get("text", ""),
                extent=[],
                provision_type=ProvisionType.SCHEDULE,
                # Provenance tracking
                provenance_source="llm_ocr",
                provenance_model=provenance.get("model"),
                provenance_prompt_version=provenance.get("prompt_version"),
                provenance_timestamp=provenance.get("timestamp"),
                provenance_response_id=provenance.get("response_id"),
            )
        )

    return section_records


def save_json_for_document(
    legislation: Legislation,
    sections: list[LegislationSection],
    pdf_url: str,
    base_dir: Path,
) -> Path:
    """Save legislation and sections as JSON using PDF URL path structure."""
    url_path = urlparse(pdf_url).path.lstrip("/")
    if url_path.startswith("historical-legislation-pdfs/"):
        url_path = url_path[28:]  # Strip container prefix

    json_path = base_dir / url_path.replace(".pdf", ".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)

    with open(json_path, "w") as f:
        json.dump({
            "legislation": legislation.model_dump(mode="json"),
            "sections": [s.model_dump(mode="json") for s in sections],
        }, f, indent=2, default=str)

    return json_path


def process_jsonl_file(
    jsonl_path: Path,
    json_backup_dir: Path | None = None,
) -> tuple[list[Legislation], list[LegislationSection]]:
    """
    Process JSONL file of PDF extractions and create Qdrant-ready records.

    Args:
        jsonl_path: Path to JSONL file with PDF extraction results
        json_backup_dir: Optional directory to save JSON backups (using URL path structure)

    Returns:
        Tuple of (legislation_records, section_records)
    """
    legislation_records = []
    section_records = []

    with open(jsonl_path, "r") as f:
        for line in f:
            if not line.strip():
                continue

            pdf_result = json.loads(line)

            # Skip failed extractions
            if not pdf_result.get("success"):
                logger.warning(f"Skipping failed extraction: {pdf_result.get('identifier')}")
                continue

            # Fetch XML metadata
            identifier = pdf_result.get("identifier", "")
            leg_type = pdf_result.get("legislation_type", "")

            # Clean up malformed identifiers
            if identifier.startswith("id/"):
                identifier = identifier[3:]  # Remove "id/" prefix

            legislation_id = f"{leg_type}/{identifier}"

            logger.info(f"Processing: {legislation_id}")

            xml_meta = fetch_xml_metadata(legislation_id)
            if not xml_meta.get("id"):
                logger.error(f"Failed to fetch XML metadata for {legislation_id}")
                continue

            # Create records
            legislation = merge_xml_and_pdf(xml_meta, pdf_result)
            sections = create_section_records(legislation, pdf_result)

            legislation_records.append(legislation)
            section_records.extend(sections)

            # Save JSON backup if requested
            if json_backup_dir:
                pdf_url = pdf_result.get("pdf_source", "")
                if pdf_url:
                    json_path = save_json_for_document(legislation, sections, pdf_url, json_backup_dir)
                    logger.info(f"💾 Saved JSON backup: {json_path}")

            logger.info(
                f"Created records for {legislation_id}: "
                f"1 legislation, {len(sections)} sections/schedules"
            )

    return legislation_records, section_records


def upload_to_qdrant(
    legislation_records: list[Legislation],
    section_records: list[LegislationSection],
) -> tuple[int, int]:
    """
    Upload legislation and section records to Qdrant with embeddings.

    Note: JSON backups are now saved during process_jsonl_file() to preserve
    the original PDF URL for path structure.

    Args:
        legislation_records: List of Legislation instances
        section_records: List of LegislationSection instances

    Returns:
        Tuple of (legislation_count, section_count) uploaded
    """
    qdrant_client = get_qdrant_client()
    uuid_namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    # Upload legislation
    logger.info(f"Generating embeddings for {len(legislation_records)} legislation records...")
    leg_points = []
    for leg in legislation_records:
        # Generate embedding text (title + type + description)
        text = f"{leg.title} {leg.type.value if leg.type else ''} {leg.description}"

        # Generate embeddings
        dense_vector = generate_dense_embedding(text)
        sparse_vector = generate_sparse_embedding(text)

        # Create UUID5 for idempotency
        point_id = str(uuid.uuid5(uuid_namespace, leg.id))

        leg_points.append(
            PointStruct(
                id=point_id,
                vector={"dense": dense_vector, "sparse": sparse_vector},
                payload=leg.model_dump(mode="json"),
            )
        )

    logger.info(f"Uploading {len(leg_points)} legislation records to Qdrant...")
    qdrant_client.upsert(
        collection_name="legislation",
        points=leg_points,
        wait=True,
    )
    logger.info(f"✅ Uploaded {len(leg_points)} legislation records")

    # Upload sections
    logger.info(f"Generating embeddings for {len(section_records)} section records...")
    section_points = []
    for section in section_records:
        # Generate embedding text (title + text)
        text = f"{section.title} {section.text}"

        # Generate embeddings
        dense_vector = generate_dense_embedding(text)
        sparse_vector = generate_sparse_embedding(text)

        # Create UUID5 for idempotency
        point_id = str(uuid.uuid5(uuid_namespace, section.id))

        section_points.append(
            PointStruct(
                id=point_id,
                vector={"dense": dense_vector, "sparse": sparse_vector},
                payload=section.model_dump(mode="json"),
            )
        )

    logger.info(f"Uploading {len(section_points)} section records to Qdrant...")
    qdrant_client.upsert(
        collection_name="legislation_section",
        points=section_points,
        wait=True,
    )
    logger.info(f"✅ Uploaded {len(section_points)} section records")

    return len(leg_points), len(section_points)
