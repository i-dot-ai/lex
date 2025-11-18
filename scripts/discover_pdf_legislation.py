"""
Discover PDF-only legislation from legislation.gov.uk Atom feeds.

Usage:
    # Discover all historical PDFs (1267-1962)
    uv run python scripts/discover_pdf_legislation.py

    # Specific year range
    uv run python scripts/discover_pdf_legislation.py --start-year 1800 --end-year 1900

    # Output to custom file
    uv run python scripts/discover_pdf_legislation.py --output data/pdf_discovered.jsonl
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from lex.core.http import HttpClient

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

http_client = HttpClient()
BASE_URL = "https://www.legislation.gov.uk"


def discover_pdfs_for_year(year: int) -> list[dict]:
    """
    Discover PDF-only legislation for a given year via Atom feed.

    Returns list of dicts with: legislation_id, pdf_url, type, year, number, title, has_xml
    """
    pdfs = []
    page = 1

    logger.info(f"Discovering PDFs for year {year}...")

    while True:
        feed_url = f"{BASE_URL}/primary+secondary/{year}/data.feed?page={page}"

        try:
            response = http_client.get(feed_url)
            if response.status_code != 200:
                logger.debug(f"No feed for year {year} page {page} (status {response.status_code})")
                break
        except Exception as e:
            logger.error(f"Error fetching feed for {year} page {page}: {e}")
            break

        soup = BeautifulSoup(response.text, "xml")
        entries = soup.find_all("entry")

        if not entries:
            break

        for entry in entries:
            leg_id = entry.find("id")
            title = entry.find("title")

            if not leg_id or not title:
                continue

            leg_id = leg_id.text.strip()
            title = title.text.strip()

            # Test if PDF-only
            pdf_doc = test_document(leg_id, title)
            if pdf_doc:
                pdfs.append(pdf_doc)

        # Check for more pages
        more_pages = soup.find("morePages")
        if not more_pages or int(more_pages.text or "0") == 0:
            break

        page += 1

    logger.info(f"Year {year}: Found {len(pdfs)} PDF-only documents")
    return pdfs


def test_document(legislation_id: str, title: str) -> dict | None:
    """
    Test if document is PDF-only.

    Returns dict if PDF-only, None if has XML body.
    """
    try:
        # Convert ID to data.xml URL
        data_url = legislation_id.replace("/id/", "/") + "/data.xml"

        response = http_client.get(data_url)
        if response.status_code != 200:
            logger.debug(f"No XML for {legislation_id} (status {response.status_code})")
            return None

        soup = BeautifulSoup(response.text, "xml")

        # Check if body exists
        has_body = soup.find("Body") is not None

        if has_body:
            # Has XML content, not PDF-only
            return None

        # PDF-only - extract PDF URL from metadata
        pdf_link = soup.find(
            "atom:link", attrs={"type": "application/pdf", "title": "Original PDF"}
        )

        pdf_url = pdf_link.get("href") if pdf_link else None

        # Parse identifier
        parts = legislation_id.split("/")
        leg_type = parts[4] if len(parts) > 4 else None
        identifier = "/".join(parts[5:]) if len(parts) > 5 else None

        return {
            "legislation_id": legislation_id,
            "pdf_url": pdf_url,
            "legislation_type": leg_type,
            "identifier": identifier,
            "title": title,
            "has_xml": True,  # Has XML metadata, just no body
            "discovered_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.warning(f"Skipping {legislation_id} due to error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Discover PDF-only legislation from Atom feeds")
    parser.add_argument("--start-year", type=int, default=1267, help="Start year (default: 1267)")
    parser.add_argument("--end-year", type=int, default=1962, help="End year (default: 1962)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/pdf_legislation_discovered.jsonl"),
        help="Output JSONL file",
    )

    args = parser.parse_args()

    logger.info(f"Discovering PDF-only legislation from {args.start_year} to {args.end_year}")
    logger.info(f"Output: {args.output}")

    total_pdfs = 0

    with open(args.output, "w") as f:
        for year in range(args.start_year, args.end_year + 1):
            pdfs = discover_pdfs_for_year(year)

            for pdf in pdfs:
                f.write(json.dumps(pdf) + "\n")
                f.flush()
                total_pdfs += 1

    logger.info(f"✅ Discovery complete: {total_pdfs} PDF-only documents found")
    logger.info(f"Output written to: {args.output}")

    # Also create CSV for convenience
    csv_path = args.output.with_suffix(".csv")
    logger.info(f"Creating CSV: {csv_path}")

    with open(args.output, "r") as f_in, open(csv_path, "w") as f_out:
        f_out.write("pdf_url,legislation_type,identifier,title\n")

        for line in f_in:
            doc = json.loads(line)
            if doc.get("pdf_url"):
                # Escape title for CSV
                title = doc["title"].replace('"', '""') if doc.get("title") else ""
                f_out.write(
                    f'{doc["pdf_url"]},{doc["legislation_type"]},{doc["identifier"]},"{title}"\n'
                )

    logger.info(f"✅ CSV written to: {csv_path}")


if __name__ == "__main__":
    main()
