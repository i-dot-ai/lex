"""Common utility functions shared across analyzers."""

import re
from typing import Optional, Tuple


def extract_year_from_message(message: str) -> Optional[int]:
    """Extract year from a log message containing legislation references."""
    # Look for patterns like /2023/, /1975/, etc.
    year_match = re.search(r"/(\d{4})/", message)
    if year_match:
        year = int(year_match.group(1))
        # Reasonable bounds check
        if 1900 <= year <= 2100:
            return year
    return None


def extract_legislation_type(message: str) -> Optional[str]:
    """Extract legislation type from a log message."""
    # Common legislation types
    types = [
        "ukpga",
        "uksi",
        "ukla",
        "ukppa",
        "ukcm",
        "ukmo",
        "ukci",
        "uksro",
        "asp",
        "asc",
        "anaw",
        "aep",
        "aip",
        "apgb",
        "aosp",
        "apni",
        "mwa",
        "mnia",
        "nia",
        "nisi",
        "nisr",
        "nisro",
        "ssi",
        "wsi",
        "gbla",
        "eur",
        "eudr",
        "eudn",
    ]

    for leg_type in types:
        if f"/{leg_type}/" in message.lower():
            return leg_type
    return None


def extract_document_id(message: str) -> Optional[str]:
    """Extract document ID from a log message."""
    # Look for patterns like http://www.legislation.gov.uk/id/ukpga/2023/52
    id_pattern = r"http://www\.legislation\.gov\.uk/id/([^/]+)/(\d{4})/(\d+)"
    match = re.search(id_pattern, message)
    if match:
        return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

    # Alternative pattern without /id/
    alt_pattern = r"legislation\.gov\.uk/([^/]+)/(\d{4})/(\d+)"
    match = re.search(alt_pattern, message)
    if match:
        return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

    return None


def extract_url_from_message(message: str) -> Optional[str]:
    """Extract legislation.gov.uk URL from log message."""
    # Look for legislation.gov.uk URLs
    url_pattern = r"https?://(?:www\.)?legislation\.gov\.uk/[^\s]+"
    match = re.search(url_pattern, message)
    if match:
        return match.group(0).rstrip(".,;)")

    # Also try to construct URL from ID if present
    id_pattern = r"http://www\.legislation\.gov\.uk/id/([^/]+)/(\d{4})/(\d+)"
    id_match = re.search(id_pattern, message)
    if id_match:
        leg_type, year, number = id_match.groups()
        return f"https://www.legislation.gov.uk/{leg_type}/{year}/{number}"

    return None


def extract_year_and_type(message: str) -> Tuple[Optional[int], Optional[str]]:
    """Extract both year and legislation type from a message."""
    year = extract_year_from_message(message)
    leg_type = extract_legislation_type(message)
    return year, leg_type


def normalize_error_message(message: str) -> str:
    """Normalize an error message by removing variable parts."""
    # Remove URLs
    normalized = re.sub(r"https?://[^\s]+", "URL", message)
    # Replace years
    normalized = re.sub(r"/\d{4}/", "/YEAR/", normalized)
    # Replace document references
    normalized = re.sub(r"/[a-zA-Z]+/\d+", "/TYPE/NUM", normalized)
    # Replace standalone numbers
    normalized = re.sub(r"\b\d+\b", "NUM", normalized)
    # Replace UUIDs
    normalized = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "UUID", normalized
    )

    return normalized


def categorize_document_type(message: str) -> Optional[str]:
    """Categorize the document type from a log message."""
    message_lower = message.lower()

    if "legislation" in message_lower:
        return "legislation"
    elif "caselaw" in message_lower or "case law" in message_lower:
        return "caselaw"
    elif "amendment" in message_lower:
        return "amendment"
    elif "explanatory" in message_lower:
        return "explanatory_note"

    # Try to infer from URL patterns
    if "caselaw" in message_lower or "/ewhc/" in message_lower or "/ewca/" in message_lower:
        return "caselaw"

    # Default to legislation if it has a legislation type
    if extract_legislation_type(message):
        return "legislation"

    return None


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"
