"""
PDF downloader for historical UK legislation.

Downloads PDFs from legislation.gov.uk and caches them locally
with the same directory structure for efficient reprocessing.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import aiohttp
from tqdm import tqdm

logger = logging.getLogger(__name__)


class LegislationPDFDownloader:
    """
    Download PDFs from legislation.gov.uk with local caching.

    Features:
    - Preserves directory structure (e.g., /aep/Ja1/7/18/pdfs/aep_Ja170018_en.pdf)
    - Skips already downloaded files
    - Concurrent downloads with rate limiting
    - Progress tracking

    Usage:
        downloader = LegislationPDFDownloader(cache_dir="data/pdfs")
        await downloader.download_batch(pdf_urls, legislation_types, identifiers)
    """

    def __init__(
        self, cache_dir: str = "data/pdfs", max_concurrent: int = 10, timeout_seconds: int = 60
    ):
        """
        Initialize PDF downloader.

        Args:
            cache_dir: Root directory for cached PDFs
            max_concurrent: Maximum concurrent downloads (default 10)
            timeout_seconds: HTTP timeout in seconds (default 60)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

        logger.info(f"PDF cache directory: {self.cache_dir.absolute()}")

    def get_local_path(self, pdf_url: str, legislation_type: str, identifier: str) -> Path:
        """
        Get local file path for a PDF, preserving legislation.gov.uk structure.

        Args:
            pdf_url: URL to PDF (e.g., http://www.legislation.gov.uk/aep/Ja1/7/18/pdfs/aep_Ja170018_en.pdf)
            legislation_type: Type code (e.g., 'aep', 'ukla')
            identifier: Identifier (e.g., 'Ja1/7/18', 'Geo3/46/122')

        Returns:
            Local path like: data/pdfs/aep/Ja1/7/18/pdfs/aep_Ja170018_en.pdf
        """
        # Extract filename from URL
        filename = pdf_url.split("/")[-1]

        # Build path: cache_dir/type/identifier/pdfs/filename
        local_path = self.cache_dir / legislation_type / identifier / "pdfs" / filename

        return local_path

    async def download_pdf(
        self,
        session: aiohttp.ClientSession,
        pdf_url: str,
        legislation_type: str,
        identifier: str,
        force: bool = False,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Download a single PDF file.

        Args:
            session: aiohttp ClientSession
            pdf_url: URL to PDF
            legislation_type: Type code
            identifier: Identifier
            force: Force re-download even if file exists

        Returns:
            Tuple of (success, local_path, error_message)
        """
        local_path = self.get_local_path(pdf_url, legislation_type, identifier)

        # Skip if already exists (unless force)
        if local_path.exists() and not force:
            logger.debug(f"Skipping (cached): {local_path}")
            return True, str(local_path), None

        # Create parent directories
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Download PDF
            async with session.get(pdf_url, timeout=self.timeout) as response:
                response.raise_for_status()

                # Write to file
                pdf_bytes = await response.read()
                with open(local_path, "wb") as f:
                    f.write(pdf_bytes)

                logger.info(f"Downloaded: {pdf_url} -> {local_path}")
                return True, str(local_path), None

        except asyncio.TimeoutError:
            error = f"Timeout downloading {pdf_url}"
            logger.error(error)
            return False, str(local_path), error

        except aiohttp.ClientError as e:
            error = f"HTTP error downloading {pdf_url}: {e}"
            logger.error(error)
            return False, str(local_path), error

        except Exception as e:
            error = f"Failed to download {pdf_url}: {e}"
            logger.error(error)
            return False, str(local_path), error

    async def download_batch(
        self,
        pdf_urls: List[str],
        legislation_types: List[str],
        identifiers: List[str],
        force: bool = False,
        show_progress: bool = True,
    ) -> List[Tuple[bool, str, Optional[str]]]:
        """
        Download multiple PDFs concurrently.

        Args:
            pdf_urls: List of PDF URLs
            legislation_types: List of legislation types (parallel to pdf_urls)
            identifiers: List of identifiers (parallel to pdf_urls)
            force: Force re-download of existing files
            show_progress: Show progress bar

        Returns:
            List of (success, local_path, error_message) tuples
        """
        if not (len(pdf_urls) == len(legislation_types) == len(identifiers)):
            raise ValueError("pdf_urls, legislation_types, and identifiers must have same length")

        semaphore = asyncio.Semaphore(self.max_concurrent)
        results = []

        async def download_with_semaphore(
            session: aiohttp.ClientSession, url: str, leg_type: str, ident: str
        ) -> Tuple[bool, str, Optional[str]]:
            async with semaphore:
                return await self.download_pdf(session, url, leg_type, ident, force)

        # Create HTTP session
        async with aiohttp.ClientSession() as session:
            # Create tasks
            tasks = [
                download_with_semaphore(session, url, leg_type, ident)
                for url, leg_type, ident in zip(pdf_urls, legislation_types, identifiers)
            ]

            # Execute with progress bar
            if show_progress:
                results = []
                for task in tqdm(
                    asyncio.as_completed(tasks), total=len(tasks), desc="Downloading PDFs"
                ):
                    result = await task
                    results.append(result)
            else:
                results = await asyncio.gather(*tasks)

        # Log summary
        successful = sum(1 for success, _, _ in results if success)
        failed = len(results) - successful
        logger.info(f"Download complete: {successful}/{len(results)} successful, {failed} failed")

        return results


async def download_from_csv(
    csv_path: str,
    cache_dir: str = "data/pdfs",
    max_concurrent: int = 10,
    limit: Optional[int] = None,
) -> List[Tuple[bool, str, Optional[str]]]:
    """
    Download PDFs from CSV file containing pdf_url, legislation_type, identifier.

    Args:
        csv_path: Path to CSV file (with headers)
        cache_dir: Root directory for cached PDFs
        max_concurrent: Maximum concurrent downloads
        limit: Optional limit on number of PDFs to download

    Returns:
        List of (success, local_path, error_message) tuples
    """
    import csv

    pdf_urls = []
    legislation_types = []
    identifiers = []

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            pdf_urls.append(row["pdf_url"])
            legislation_types.append(row["legislation_type"])
            identifiers.append(row["identifier"])

    logger.info(f"Loaded {len(pdf_urls)} PDFs from {csv_path}")

    downloader = LegislationPDFDownloader(cache_dir=cache_dir, max_concurrent=max_concurrent)
    return await downloader.download_batch(pdf_urls, legislation_types, identifiers)
