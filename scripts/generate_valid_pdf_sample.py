"""
Generate a valid sample of PDF URLs by extracting from XML metadata.

This script:
1. Reads random entries from the existing CSV
2. Extracts correct PDF URLs from legislation.gov.uk XML metadata
3. Creates a new CSV with valid URLs for batch processing
"""

import csv
import random
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bs4 import BeautifulSoup
from lex.core.http import HttpClient
from tqdm import tqdm

http_client = HttpClient()


def extract_pdf_url_from_xml(legislation_id: str) -> tuple[bool, str, str]:
    """
    Extract PDF URL from legislation XML metadata.

    Args:
        legislation_id: Format like http://www.legislation.gov.uk/id/ukpga/Geo3/41/90

    Returns:
        (success, pdf_url, error_message)
    """
    try:
        # Convert ID URL to data.xml URL
        data_url = legislation_id.replace("/id/", "/") + "/data.xml"

        # Fetch XML metadata
        response = http_client.get(data_url)
        response.raise_for_status()

        # Parse XML to find PDF URL
        soup = BeautifulSoup(response.content, "xml")

        # Look for atom:link with type="application/pdf" and title="Original PDF"
        pdf_link = soup.find(
            "atom:link", attrs={"type": "application/pdf", "title": "Original PDF"}
        )

        if pdf_link and pdf_link.get("href"):
            pdf_url = pdf_link.get("href")
            return True, pdf_url, None
        else:
            return False, "", "No PDF link found in XML"

    except Exception as e:
        return False, "", str(e)


def extract_legislation_id_from_url(url: str) -> str:
    """Extract legislation ID from various URL formats in the CSV."""
    # Remove trailing PDF path or error messages
    url = url.split("/pdfs/")[0]
    url = url.split("/data.xml")[0]

    # If it's already an /id/ URL, return as is
    if "/id/" in url:
        return url

    # Otherwise, convert to /id/ format
    # http://www.legislation.gov.uk/ukpga/Geo5/6-7/38
    # -> http://www.legislation.gov.uk/id/ukpga/Geo5/6-7/38
    if url.startswith("http://www.legislation.gov.uk/"):
        url = url.replace("http://www.legislation.gov.uk/", "http://www.legislation.gov.uk/id/")

    return url


def main():
    input_csv = Path("data/pdf_only_legislation_complete.csv")
    output_csv = Path("data/pdf_sample_20_v3.csv")
    sample_size = 20

    print(f"Reading {input_csv}...")

    # Read all valid entries from CSV
    valid_entries = []
    with open(input_csv, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row["pdf_url"]

            # Skip error messages and invalid entries
            if "database disk image is malformed" in url:
                continue
            if url.startswith("http://www.legislation.gov.uk/id/"):
                # /id/ URLs are not PDFs, but we can extract PDF URL from them
                valid_entries.append(row)
            elif "/pdfs/" in url:
                # PDF URLs (even if malformed)
                valid_entries.append(row)

    print(f"Found {len(valid_entries)} valid entries")

    # Take random sample
    sample = random.sample(valid_entries, min(sample_size, len(valid_entries)))
    print(f"Selected {len(sample)} random entries")

    # Extract correct PDF URLs
    results = []
    print("\nExtracting PDF URLs from XML metadata...")

    for row in tqdm(sample):
        legislation_id = extract_legislation_id_from_url(row["pdf_url"])
        success, pdf_url, error = extract_pdf_url_from_xml(legislation_id)

        if success:
            results.append(
                {
                    "pdf_url": pdf_url,
                    "legislation_type": row["legislation_type"],
                    "identifier": row["identifier"],
                }
            )
        else:
            print(f"  Failed to extract PDF URL for {legislation_id}: {error}")

    print(f"\nSuccessfully extracted {len(results)}/{len(sample)} PDF URLs")

    # Write to output CSV
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["pdf_url", "legislation_type", "identifier"])
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote {len(results)} entries to {output_csv}")


if __name__ == "__main__":
    main()
