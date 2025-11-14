"""
Batch processing for PDF digitization from CSV.
"""

import asyncio
import csv
import json
import logging
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiohttp

from lex.pdf_digitization.blob_uploader import LegislationBlobUploader
from lex.pdf_digitization.metadata import fetch_xml_metadata
from lex.pdf_digitization.models import ExtractionResult
from lex.pdf_digitization.processor import LegislationPDFProcessor

logger = logging.getLogger(__name__)


def load_completed_pdfs(output_path: Optional[Path]) -> set[str]:
    """
    Load set of completed PDF identifiers from existing JSONL output file.

    Args:
        output_path: Path to JSONL output file

    Returns:
        Set of completed identifiers (format: "legislation_type/identifier")
    """
    if not output_path or not output_path.exists():
        return set()

    completed = set()
    with open(output_path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                result = json.loads(line)
                # Build identifier from result
                leg_type = result.get("legislation_type")
                identifier = result.get("identifier")
                if leg_type and identifier:
                    completed.add(f"{leg_type}/{identifier}")
            except json.JSONDecodeError:
                continue

    logger.info(f"Found {len(completed)} completed PDFs in output file")
    return completed


async def process_pdf_batch_from_csv(
    csv_path: Path,
    max_concurrent: int = 10,
    output_path: Optional[Path] = None,
) -> AsyncGenerator[ExtractionResult, None]:
    """
    Process PDFs from CSV file: fetch metadata, upload to blob, OCR with GPT-5-mini.

    Resume logic: PDFs already in output JSONL file are skipped.
    Blob storage: Existing blobs are reused (optimization to avoid re-upload).

    CSV format: pdf_url, legislation_type, identifier

    Args:
        csv_path: Path to CSV file
        max_concurrent: Maximum concurrent processing (default 10)
        output_path: Path to output JSONL file (for resume capability)

    Yields:
        ExtractionResult for each processed PDF
    """
    logger.info(f"Starting batch processing from: {csv_path}")

    # Load completed PDFs for resume capability
    completed_pdfs = load_completed_pdfs(output_path)

    # Initialize uploader and processor
    uploader = LegislationBlobUploader(max_concurrent=max_concurrent)
    processor = LegislationPDFProcessor()

    try:
        # Read CSV
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)

        # Filter out already-completed PDFs
        rows_to_process = []
        skipped_count = 0
        for row in rows:
            pdf_id = f"{row['legislation_type']}/{row['identifier']}"
            if pdf_id in completed_pdfs:
                skipped_count += 1
            else:
                rows_to_process.append(row)

        if skipped_count > 0:
            logger.info(f"Resuming: skipped {skipped_count} already-completed PDFs from JSONL")

        remaining = len(rows_to_process)
        logger.info(f"Found {total} PDFs total, {remaining} remaining to process")

        # Process with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        completed = 0

        async def process_single(row: dict) -> Optional[ExtractionResult]:
            nonlocal completed

            async with semaphore:
                pdf_url = row["pdf_url"]
                legislation_type = row["legislation_type"]
                identifier = row["identifier"]

                try:
                    # Timeout wrapper: max 20 minutes per PDF to prevent hanging
                    async with asyncio.timeout(1200):  # 20 minutes
                        # Step 1: Fetch metadata from legislation.gov.uk XML
                        logger.info(
                            f"[{completed + 1}/{remaining}] Processing: {legislation_type}/{identifier}"
                        )
                        metadata = fetch_xml_metadata(legislation_type, identifier)

                        # Get page count for chunking decision
                        page_count = (
                            metadata.pdf.page_count
                            if metadata and metadata.pdf and metadata.pdf.page_count
                            else None
                        )

                        # Step 2: Upload to Azure Blob (with automatic chunking for large PDFs)
                        async with aiohttp.ClientSession(
                            timeout=aiohttp.ClientTimeout(
                                total=900,  # 15 min total per request
                                connect=60,  # 60s to establish connection
                                sock_read=120,  # 120s between socket reads
                            )
                        ) as session:
                            if page_count:
                                # Use chunking-aware uploader
                                upload_result = await uploader.process_pdf_with_chunking(
                                    session, pdf_url, legislation_type, identifier, page_count
                                )
                            else:
                                # Fallback to single upload if page count unknown
                                upload_result = await uploader.process_pdf(
                                    session, pdf_url, legislation_type, identifier
                                )

                        # Step 3: Process PDF with OCR (handle both single and chunked results)
                        if isinstance(upload_result, list):
                            # Chunked result: List[(success, sas_url, blob_name, error, start_page, end_page)]
                            if not upload_result or not upload_result[0][0]:
                                logger.error(f"Failed to upload chunks for {pdf_url}")
                                completed += 1
                                return None

                            # Extract chunk URLs
                            chunk_urls = [
                                (sas_url, start_page, end_page)
                                for success, sas_url, blob_name, error, start_page, end_page in upload_result
                                if success
                            ]

                            logger.info(f"Processing {len(chunk_urls)} chunks for {legislation_type}/{identifier}")

                            result = await processor.process_large_pdf_chunked(
                                chunk_urls=chunk_urls,
                                legislation_type=legislation_type,
                                identifier=identifier,
                                metadata=metadata,
                            )
                        else:
                            # Single PDF result: (success, sas_url, blob_name, error)
                            success, sas_url, blob_name, error = upload_result

                            if not success:
                                logger.error(f"Failed to upload {pdf_url}: {error}")
                                completed += 1
                                return None

                            result = await processor.process_pdf(
                                pdf_url=sas_url,
                                legislation_type=legislation_type,
                                identifier=identifier,
                                metadata=metadata,
                                trace_name=f"batch_{legislation_type}_{identifier.replace('/', '_')}",
                            )

                        completed += 1
                        logger.info(
                            f"[{completed}/{remaining}] Completed: {legislation_type}/{identifier} - "
                            f"{result.provenance.output_tokens} tokens, "
                            f"{result.provenance.processing_time_seconds:.1f}s"
                        )

                        return result

                except asyncio.TimeoutError:
                    completed += 1
                    logger.error(
                        f"Timeout processing {legislation_type}/{identifier} (exceeded 20 minutes)"
                    )
                    return None

                except Exception as e:
                    completed += 1
                    logger.error(
                        f"Error processing {legislation_type}/{identifier}: {e}", exc_info=True
                    )
                    return None

        # Process all PDFs concurrently
        tasks = [process_single(row) for row in rows_to_process]

        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                yield result

    finally:
        await processor.close()
        logger.info(f"Batch processing complete: {csv_path}")


async def process_single_pdf(
    pdf_url: str, legislation_type: str, identifier: str
) -> ExtractionResult:
    """
    Process a single PDF: fetch metadata, upload to blob, OCR.

    Args:
        pdf_url: URL to PDF on legislation.gov.uk
        legislation_type: e.g., 'ukpga', 'aep'
        identifier: e.g., 'Edw7/6/19'

    Returns:
        ExtractionResult with provenance
    """
    logger.info(f"Processing single PDF: {legislation_type}/{identifier}")

    # Fetch metadata
    metadata = fetch_xml_metadata(legislation_type, identifier)

    # Upload to blob
    uploader = LegislationBlobUploader()
    async with aiohttp.ClientSession() as session:
        success, sas_url, blob_name, error = await uploader.process_pdf(
            session, pdf_url, legislation_type, identifier
        )

    if not success:
        raise RuntimeError(f"Failed to upload PDF: {error}")

    # Process with OCR
    processor = LegislationPDFProcessor()
    try:
        result = await processor.process_pdf(
            pdf_url=sas_url,
            legislation_type=legislation_type,
            identifier=identifier,
            metadata=metadata,
            trace_name=f"single_{legislation_type}_{identifier.replace('/', '_')}",
        )
        return result
    finally:
        await processor.close()
