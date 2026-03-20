#!/usr/bin/env python3
"""
Audit Qdrant data coverage by year, type, and provenance.

Produces a summary table showing document counts across time periods,
legislation types, and content sources (XML vs LLM-OCR).

Usage:
    uv run python scripts/audit_data_coverage.py
    uv run python scripts/audit_data_coverage.py --amendments-check ukpga/1998/42
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    Range,
)

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lex.core.qdrant_client import qdrant_client
from lex.settings import (
    AMENDMENT_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

YEAR_BUCKETS = [
    ("Pre-1800", None, 1799),
    ("1800-1900", 1800, 1900),
    ("1901-1962", 1901, 1962),
    ("1963-2000", 1963, 2000),
    ("2001-2025", 2001, 2025),
]

KEY_LEGISLATION_TYPES = ["ukpga", "uksi", "ukla", "asp", "asc", "anaw", "nia", "nisr"]


def count_with_filter(collection: str, conditions: list | None = None) -> int:
    """Count documents in a collection with optional filter conditions."""
    count_filter = Filter(must=conditions) if conditions else None
    result = qdrant_client.count(
        collection_name=collection,
        count_filter=count_filter,
        exact=True,
    )
    return result.count


def audit_legislation():
    """Audit the legislation collection by year bucket, type, and provenance."""
    logger.info("=" * 70)
    logger.info("LEGISLATION COLLECTION")
    logger.info("=" * 70)

    total = count_with_filter(LEGISLATION_COLLECTION)
    xml_count = count_with_filter(
        LEGISLATION_COLLECTION,
        [FieldCondition(key="provenance_source", match=MatchValue(value="xml"))],
    )
    ocr_count = count_with_filter(
        LEGISLATION_COLLECTION,
        [FieldCondition(key="provenance_source", match=MatchValue(value="llm_ocr"))],
    )
    null_prov = total - xml_count - ocr_count

    logger.info(f"\nTotal: {total:,}")
    logger.info(f"  XML: {xml_count:,}  |  LLM-OCR: {ocr_count:,}  |  No provenance: {null_prov:,}")

    # By year bucket
    logger.info("\nBy year range:")
    logger.info(f"  {'Period':<15} {'Total':>8} {'XML':>8} {'OCR':>8} {'None':>8}")
    logger.info("  " + "-" * 50)

    for label, year_from, year_to in YEAR_BUCKETS:
        year_conditions = []
        if year_from is not None:
            year_conditions.append(FieldCondition(key="year", range=Range(gte=year_from)))
        if year_to is not None:
            year_conditions.append(FieldCondition(key="year", range=Range(lte=year_to)))

        bucket_total = count_with_filter(LEGISLATION_COLLECTION, year_conditions)

        xml_conds = year_conditions + [
            FieldCondition(key="provenance_source", match=MatchValue(value="xml"))
        ]
        ocr_conds = year_conditions + [
            FieldCondition(key="provenance_source", match=MatchValue(value="llm_ocr"))
        ]
        bucket_xml = count_with_filter(LEGISLATION_COLLECTION, xml_conds)
        bucket_ocr = count_with_filter(LEGISLATION_COLLECTION, ocr_conds)
        bucket_none = bucket_total - bucket_xml - bucket_ocr

        logger.info(
            f"  {label:<15} {bucket_total:>8,} {bucket_xml:>8,} {bucket_ocr:>8,} {bucket_none:>8,}"
        )

    # By type (top types only)
    logger.info("\nBy legislation type:")
    logger.info(f"  {'Type':<10} {'Total':>8} {'XML':>8} {'OCR':>8}")
    logger.info("  " + "-" * 35)

    for leg_type in KEY_LEGISLATION_TYPES:
        type_conds = [FieldCondition(key="type", match=MatchValue(value=leg_type))]
        type_total = count_with_filter(LEGISLATION_COLLECTION, type_conds)

        xml_conds = type_conds + [
            FieldCondition(key="provenance_source", match=MatchValue(value="xml"))
        ]
        ocr_conds = type_conds + [
            FieldCondition(key="provenance_source", match=MatchValue(value="llm_ocr"))
        ]
        type_xml = count_with_filter(LEGISLATION_COLLECTION, xml_conds)
        type_ocr = count_with_filter(LEGISLATION_COLLECTION, ocr_conds)

        if type_total > 0:
            logger.info(f"  {leg_type:<10} {type_total:>8,} {type_xml:>8,} {type_ocr:>8,}")


def audit_sections():
    """Audit the legislation_section collection."""
    logger.info("\n" + "=" * 70)
    logger.info("LEGISLATION_SECTION COLLECTION")
    logger.info("=" * 70)

    total = count_with_filter(LEGISLATION_SECTION_COLLECTION)
    ocr_count = count_with_filter(
        LEGISLATION_SECTION_COLLECTION,
        [FieldCondition(key="provenance_source", match=MatchValue(value="llm_ocr"))],
    )
    logger.info(f"\nTotal: {total:,}")
    logger.info(f"  LLM-OCR: {ocr_count:,}  |  XML/None: {total - ocr_count:,}")

    # By year bucket
    logger.info("\nBy year range:")
    logger.info(f"  {'Period':<15} {'Total':>10} {'OCR':>10}")
    logger.info("  " + "-" * 38)

    for label, year_from, year_to in YEAR_BUCKETS:
        year_conditions = []
        if year_from is not None:
            year_conditions.append(
                FieldCondition(key="legislation_year", range=Range(gte=year_from))
            )
        if year_to is not None:
            year_conditions.append(FieldCondition(key="legislation_year", range=Range(lte=year_to)))

        bucket_total = count_with_filter(LEGISLATION_SECTION_COLLECTION, year_conditions)
        ocr_conds = year_conditions + [
            FieldCondition(key="provenance_source", match=MatchValue(value="llm_ocr"))
        ]
        bucket_ocr = count_with_filter(LEGISLATION_SECTION_COLLECTION, ocr_conds)

        logger.info(f"  {label:<15} {bucket_total:>10,} {bucket_ocr:>10,}")

    # Count sections with null legislation_year (broken regnal year parsing)
    # Qdrant doesn't support "is null" directly, so estimate by subtracting
    # all year-filtered counts from total
    all_with_year = count_with_filter(
        LEGISLATION_SECTION_COLLECTION,
        [FieldCondition(key="legislation_year", range=Range(gte=0))],
    )
    null_year = total - all_with_year
    logger.info(f"\n  Sections with null year: {null_year:,} (broken regnal year parsing)")


def audit_amendments(check_legislation_ids: list[str] | None = None):
    """Audit the amendment collection."""
    logger.info("\n" + "=" * 70)
    logger.info("AMENDMENT COLLECTION")
    logger.info("=" * 70)

    total = count_with_filter(AMENDMENT_COLLECTION)
    logger.info(f"\nTotal: {total:,}")

    # By affecting_year
    logger.info("\nBy affecting_year range:")
    logger.info(f"  {'Period':<15} {'Count':>10}")
    logger.info("  " + "-" * 28)

    for label, year_from, year_to in YEAR_BUCKETS:
        year_conditions = []
        if year_from is not None:
            year_conditions.append(FieldCondition(key="affecting_year", range=Range(gte=year_from)))
        if year_to is not None:
            year_conditions.append(FieldCondition(key="affecting_year", range=Range(lte=year_to)))
        bucket_count = count_with_filter(AMENDMENT_COLLECTION, year_conditions)
        logger.info(f"  {label:<15} {bucket_count:>10,}")

    # Check specific legislation if requested
    if check_legislation_ids:
        logger.info("\nAmendment coverage for specific legislation:")
        for leg_id in check_legislation_ids:
            # Build the full URL pattern used in changed_url
            url_pattern = f"http://www.legislation.gov.uk/id/{leg_id}"

            changed_count = count_with_filter(
                AMENDMENT_COLLECTION,
                [FieldCondition(key="changed_url", match=MatchValue(value=url_pattern))],
            )
            affecting_count = count_with_filter(
                AMENDMENT_COLLECTION,
                [FieldCondition(key="affecting_url", match=MatchValue(value=url_pattern))],
            )

            # Also try with https and without /id/
            alt_patterns = [
                f"https://www.legislation.gov.uk/id/{leg_id}",
                f"http://www.legislation.gov.uk/{leg_id}",
                f"https://www.legislation.gov.uk/{leg_id}",
            ]

            for alt in alt_patterns:
                c = count_with_filter(
                    AMENDMENT_COLLECTION,
                    [FieldCondition(key="changed_url", match=MatchValue(value=alt))],
                )
                if c > 0:
                    changed_count += c
                a = count_with_filter(
                    AMENDMENT_COLLECTION,
                    [FieldCondition(key="affecting_url", match=MatchValue(value=alt))],
                )
                if a > 0:
                    affecting_count += a

            logger.info(f"  {leg_id}: changed_by={changed_count}, affecting={affecting_count}")


def audit_explanatory_notes():
    """Audit the explanatory_note collection."""
    logger.info("\n" + "=" * 70)
    logger.info("EXPLANATORY_NOTE COLLECTION")
    logger.info("=" * 70)

    total = count_with_filter(EXPLANATORY_NOTE_COLLECTION)
    logger.info(f"\nTotal: {total:,}")

    # Check specific legislation
    check_ids = [
        "http://www.legislation.gov.uk/id/ukpga/2024/8",
        "http://www.legislation.gov.uk/id/ukpga/1998/42",
        "http://www.legislation.gov.uk/id/ukpga/2023/32",
    ]

    logger.info("\nExplanatory notes for specific legislation:")
    for leg_id in check_ids:
        count = count_with_filter(
            EXPLANATORY_NOTE_COLLECTION,
            [FieldCondition(key="legislation_id", match=MatchValue(value=leg_id))],
        )
        logger.info(f"  {leg_id}: {count} notes")


def sample_amendments():
    """Sample a few amendments to check URL format patterns."""
    logger.info("\nSampling amendment URL patterns:")
    result = qdrant_client.scroll(
        collection_name=AMENDMENT_COLLECTION,
        limit=5,
        with_payload=["changed_url", "affecting_url", "affecting_year", "changed_legislation"],
    )
    for point in result[0]:
        payload = point.payload
        logger.info(
            f"  changed_url={payload.get('changed_url', 'N/A')[:80]}, "
            f"affecting_year={payload.get('affecting_year', 'N/A')}, "
            f"changed_legislation={payload.get('changed_legislation', 'N/A')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Audit Qdrant data coverage")
    parser.add_argument(
        "--amendments-check",
        nargs="*",
        default=["ukpga/1998/42", "ukpga/2024/8", "ukpga/2010/15"],
        help="Legislation IDs to check amendment coverage for",
    )
    args = parser.parse_args()

    logger.info("Qdrant Data Coverage Audit")
    logger.info("=" * 70)

    audit_legislation()
    audit_sections()
    audit_amendments(args.amendments_check)
    sample_amendments()
    audit_explanatory_notes()

    logger.info("\n" + "=" * 70)
    logger.info("Audit complete.")


if __name__ == "__main__":
    main()
