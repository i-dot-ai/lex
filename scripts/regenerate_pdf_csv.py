"""
Regenerate PDF CSV by adding newly discovered PDF-only documents from section scraper.

This script:
1. Loads existing PDF CSV
2. Extracts PDF-only failures from section scraper tracking files
3. Fetches correct PDF URLs from legislation.gov.uk XML
4. Creates updated CSV with all PDFs to process
"""

import csv
import json
import requests
from pathlib import Path
from collections import defaultdict
from bs4 import BeautifulSoup
from tqdm import tqdm


def extract_pdf_url_from_xml(legislation_type: str, identifier: str) -> tuple[bool, str, str]:
    """
    Extract PDF URL from legislation XML metadata.

    Args:
        legislation_type: e.g. 'ukpga', 'uksi'
        identifier: e.g. '2020/123' or 'Geo3/41/90'

    Returns:
        (success, pdf_url, error_message)
    """
    try:
        # Build data.xml URL
        data_url = f"https://www.legislation.gov.uk/{legislation_type}/{identifier}/data.xml"

        # Fetch XML metadata
        response = requests.get(data_url, timeout=30)
        response.raise_for_status()

        # Parse XML to find PDF URL
        soup = BeautifulSoup(response.content, "xml")

        # Look for atom:link with type="application/pdf" and title="Original PDF"
        pdf_link = soup.find("atom:link", attrs={"type": "application/pdf", "title": "Original PDF"})

        if pdf_link and pdf_link.get("href"):
            pdf_url = pdf_link.get("href")
            return True, pdf_url, None
        else:
            return False, "", "No PDF link found in XML"

    except Exception as e:
        return False, "", str(e)


def main():
    print("=" * 80)
    print("REGENERATING PDF CSV WITH NEW DISCOVERIES")
    print("=" * 80)

    # Step 1: Load existing CSV
    existing_csv = Path("data/pdf_complete_1963_2025.csv")
    existing_pdfs = set()
    existing_rows = []

    print(f"\n1. Loading existing CSV: {existing_csv}")

    with open(existing_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdf_id = f"{row['legislation_type']}/{row['identifier']}"
            existing_pdfs.add(pdf_id)
            existing_rows.append(row)

    print(f"   Found {len(existing_rows)} existing PDFs")

    # Step 2: Collect new PDF-only failures from tracking
    print(f"\n2. Scanning section scraper failure tracking files...")

    new_pdf_candidates = []
    failure_files = list(Path('data/tracking').glob('*failures.jsonl'))

    print(f"   Found {len(failure_files)} failure files")

    for file in failure_files:
        with open(file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    error = entry.get('error', '')

                    # Check for PDF-only error
                    if 'only exists as a PDF' in error:
                        url = entry.get('url', '')
                        if '/data.xml' in url:
                            # Extract type and identifier from URL
                            url_clean = url.replace('/data.xml', '')
                            url_parts = url_clean.split('/')

                            # Find legislation type
                            known_types = ['uksi', 'ukpga', 'eur', 'eudr', 'eudn', 'nisr',
                                         'ukla', 'asp', 'ssi', 'wsi', 'nisi', 'nia']

                            leg_type_idx = None
                            for i, part in enumerate(url_parts):
                                if part in known_types:
                                    leg_type_idx = i
                                    break

                            if leg_type_idx and leg_type_idx < len(url_parts) - 1:
                                leg_type = url_parts[leg_type_idx]
                                identifier = '/'.join(url_parts[leg_type_idx + 1:])

                                pdf_id = f"{leg_type}/{identifier}"

                                # Only add if not already in existing CSV
                                if pdf_id not in existing_pdfs:
                                    new_pdf_candidates.append({
                                        'legislation_type': leg_type,
                                        'identifier': identifier
                                    })
                                    existing_pdfs.add(pdf_id)  # Avoid duplicates
                except:
                    continue

    print(f"   Found {len(new_pdf_candidates)} new PDF-only documents")

    # Show breakdown
    new_by_type = defaultdict(int)
    for doc in new_pdf_candidates:
        new_by_type[doc['legislation_type']] += 1

    print(f"\n   Breakdown by type:")
    for leg_type, count in sorted(new_by_type.items(), key=lambda x: -x[1]):
        print(f"      {leg_type}: {count}")

    # Step 3: Extract PDF URLs from XML for new documents
    print(f"\n3. Extracting PDF URLs from XML metadata...")

    new_rows = []
    failed = 0

    for doc in tqdm(new_pdf_candidates, desc="   Processing"):
        success, pdf_url, error = extract_pdf_url_from_xml(
            doc['legislation_type'],
            doc['identifier']
        )

        if success:
            new_rows.append({
                'pdf_url': pdf_url,
                'legislation_type': doc['legislation_type'],
                'identifier': doc['identifier']
            })
        else:
            failed += 1

    print(f"   Successfully extracted {len(new_rows)} PDF URLs")
    print(f"   Failed: {failed}")

    # Step 4: Combine and write new CSV
    output_csv = Path("data/pdf_complete_updated.csv")
    all_rows = existing_rows + new_rows

    print(f"\n4. Writing updated CSV: {output_csv}")
    print(f"   Total PDFs: {len(all_rows)}")

    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['pdf_url', 'legislation_type', 'identifier'])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n{'=' * 80}")
    print(f"COMPLETE")
    print(f"{'=' * 80}")
    print(f"Original CSV: {len(existing_rows)} PDFs")
    print(f"New PDFs:     {len(new_rows)} PDFs")
    print(f"Total:        {len(all_rows)} PDFs")
    print(f"\nOutput: {output_csv}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
