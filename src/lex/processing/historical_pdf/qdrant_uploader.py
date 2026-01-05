"""
Simple uploader to merge XML metadata with PDF extractions and upload to Qdrant.
"""

import json
import logging
import random
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import PointStruct

from lex.core.embeddings import (
    generate_dense_embeddings_batch,
    generate_sparse_embeddings_batch,
)
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

# Retry configuration for Qdrant operations
QDRANT_MAX_RETRIES = 5
QDRANT_BASE_BACKOFF = 2.0  # seconds
QDRANT_MAX_BACKOFF = 60.0  # seconds

T = TypeVar("T")


def retry_qdrant_operation(operation: Callable[[], T], operation_name: str) -> T:
    """
    Retry a Qdrant operation with exponential backoff for transient errors.

    Args:
        operation: Function to execute
        operation_name: Name for logging

    Returns:
        Result from operation

    Raises:
        Exception: If operation fails after all retries
    """
    for attempt in range(QDRANT_MAX_RETRIES):
        try:
            return operation()
        except UnexpectedResponse as e:
            # Check if it's a retryable error (502, 503, 504, connection errors)
            is_retryable = False
            error_str = str(e)

            # Check for status code in exception attributes or message
            if hasattr(e, "status_code"):
                is_retryable = e.status_code in [502, 503, 504]
            # Parse status code from exception message (e.g., "Unexpected Response: 503")
            elif any(
                code in error_str
                for code in [
                    "502",
                    "503",
                    "504",
                    "Bad Gateway",
                    "Service Unavailable",
                    "Gateway Timeout",
                ]
            ):
                is_retryable = True

            if not is_retryable or attempt == QDRANT_MAX_RETRIES - 1:
                logger.error(f"Qdrant {operation_name} failed after {attempt + 1} attempts: {e}")
                raise

            # Exponential backoff with jitter
            backoff = min(QDRANT_BASE_BACKOFF * (2**attempt), QDRANT_MAX_BACKOFF)
            jitter = random.uniform(0, backoff * 0.1)
            sleep_time = backoff + jitter

            logger.warning(
                f"Qdrant {operation_name} failed with {e}, retrying in {sleep_time:.1f}s (attempt {attempt + 1}/{QDRANT_MAX_RETRIES})"
            )
            time.sleep(sleep_time)

        except Exception as e:
            # Non-retryable errors
            logger.error(f"Non-retryable error in Qdrant {operation_name}: {type(e).__name__}: {e}")
            raise

    raise Exception(f"Qdrant {operation_name} failed after {QDRANT_MAX_RETRIES} retries")


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
        try:
            extracted_data = json.loads(extracted_data)
        except json.JSONDecodeError as e:
            logger.error(f"Malformed JSON in extracted_data: {e}")
            raise ValueError(f"Invalid JSON in extracted_data: {e}")

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
        json.dump(
            {
                "legislation": legislation.model_dump(mode="json"),
                "sections": [s.model_dump(mode="json") for s in sections],
            },
            f,
            indent=2,
            default=str,
        )

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
            try:
                legislation = merge_xml_and_pdf(xml_meta, pdf_result)
                sections = create_section_records(legislation, pdf_result)

                legislation_records.append(legislation)
                section_records.extend(sections)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"Skipping {legislation_id} due to malformed data: {e}")
                continue

            # Save JSON backup if requested
            if json_backup_dir:
                pdf_url = pdf_result.get("pdf_source", "")
                if pdf_url:
                    json_path = save_json_for_document(
                        legislation, sections, pdf_url, json_backup_dir
                    )
                    logger.info(f"💾 Saved JSON backup: {json_path}")

            logger.info(
                f"Created records for {legislation_id}: "
                f"1 legislation, {len(sections)} sections/schedules"
            )

    return legislation_records, section_records


def upload_to_qdrant(
    legislation_records: list[Legislation],
    section_records: list[LegislationSection],
    batch_size: int = 100,
    legislation_offset: int = 0,
    section_offset: int = 0,
) -> tuple[int, int]:
    """
    Upload legislation and section records to Qdrant with embeddings in batches.

    Note: JSON backups are now saved during process_jsonl_file() to preserve
    the original PDF URL for path structure.

    Args:
        legislation_records: List of Legislation instances
        section_records: List of LegislationSection instances
        batch_size: Number of records to upload per batch (default: 100)
        legislation_offset: Skip first N legislation records (default: 0)
        section_offset: Skip first N section records (default: 0)

    Returns:
        Tuple of (legislation_count, section_count) uploaded
    """
    qdrant_client = get_qdrant_client()
    uuid_namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    # Upload legislation in batches (OPTIMIZED with parallel batch embeddings)
    total_leg = len(legislation_records)

    if legislation_offset > 0:
        logger.info(
            f"⏭️  Skipping first {legislation_offset:,} legislation records (already uploaded)"
        )
        logger.info(
            f"📤 Uploading {total_leg - legislation_offset:,} remaining legislation records in batches of {batch_size}..."
        )
    else:
        logger.info(f"📤 Uploading {total_leg:,} legislation records in batches of {batch_size}...")

    logger.info("⚡ Using parallel batch embeddings (10 workers for dense, bulk for sparse)")

    leg_uploaded = 0
    for i in range(legislation_offset, total_leg, batch_size):
        batch = legislation_records[i : i + batch_size]

        # Collect all texts from batch
        texts = [
            f"{leg.title} {leg.type.value if leg.type else ''} {leg.description}" for leg in batch
        ]

        # Generate embeddings in parallel (MUCH FASTER!)
        dense_vectors = generate_dense_embeddings_batch(texts, max_workers=10)
        sparse_vectors = generate_sparse_embeddings_batch(texts)

        # Assemble points
        leg_points = []
        for leg, dense_vec, sparse_vec in zip(batch, dense_vectors, sparse_vectors):
            point_id = str(uuid.uuid5(uuid_namespace, leg.id))
            leg_points.append(
                PointStruct(
                    id=point_id,
                    vector={"dense": dense_vec, "sparse": sparse_vec},
                    payload=leg.model_dump(mode="json"),
                )
            )

        # Upload batch with retry logic
        retry_qdrant_operation(
            lambda: qdrant_client.upsert(
                collection_name="legislation",
                points=leg_points,
                wait=True,
            ),
            operation_name=f"legislation upsert batch {i // batch_size + 1}",
        )
        leg_uploaded += len(leg_points)

        # Log progress every 10 batches or at end
        if (i // batch_size + 1) % 10 == 0 or leg_uploaded == total_leg:
            logger.info(
                f"  Progress: {leg_uploaded:,}/{total_leg:,} legislation ({leg_uploaded * 100 // total_leg}%)"
            )

    logger.info(f"✅ Uploaded {leg_uploaded:,} legislation records")

    # Upload sections in batches (OPTIMIZED with parallel batch embeddings)
    total_sections = len(section_records)

    if section_offset > 0:
        logger.info(f"⏭️  Skipping first {section_offset:,} section records (already uploaded)")
        logger.info(
            f"📤 Uploading {total_sections - section_offset:,} remaining section records in batches of {batch_size}..."
        )
    else:
        logger.info(
            f"📤 Uploading {total_sections:,} section records in batches of {batch_size}..."
        )

    logger.info("⚡ Using parallel batch embeddings (10 workers for dense, bulk for sparse)")

    sections_uploaded = 0
    for i in range(section_offset, total_sections, batch_size):
        batch = section_records[i : i + batch_size]

        # Collect all texts from batch
        texts = [f"{section.title} {section.text}" for section in batch]

        # Generate embeddings in parallel (MUCH FASTER!)
        dense_vectors = generate_dense_embeddings_batch(texts, max_workers=10)
        sparse_vectors = generate_sparse_embeddings_batch(texts)

        # Assemble points
        section_points = []
        for section, dense_vec, sparse_vec in zip(batch, dense_vectors, sparse_vectors):
            point_id = str(uuid.uuid5(uuid_namespace, section.id))
            section_points.append(
                PointStruct(
                    id=point_id,
                    vector={"dense": dense_vec, "sparse": sparse_vec},
                    payload=section.model_dump(mode="json"),
                )
            )

        # Upload batch with retry logic
        retry_qdrant_operation(
            lambda: qdrant_client.upsert(
                collection_name="legislation_section",
                points=section_points,
                wait=True,
            ),
            operation_name=f"section upsert batch {i // batch_size + 1}",
        )
        sections_uploaded += len(section_points)

        # Log progress every 10 batches or at end
        if (i // batch_size + 1) % 10 == 0 or sections_uploaded == total_sections:
            logger.info(
                f"  Progress: {sections_uploaded:,}/{total_sections:,} sections ({sections_uploaded * 100 // total_sections}%)"
            )

    logger.info(f"✅ Uploaded {sections_uploaded:,} section records")

    return leg_uploaded, sections_uploaded
