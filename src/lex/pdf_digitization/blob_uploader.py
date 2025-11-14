"""
Azure Blob Storage uploader for historical UK legislation PDFs.

Downloads PDFs from legislation.gov.uk and uploads to Azure Blob Storage
with SAS token generation for Azure OpenAI access.

Supports automatic PDF chunking for large documents.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Union

import aiohttp
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas
from tqdm import tqdm

from lex.pdf_digitization.pdf_splitter import split_pdf_into_chunks

logger = logging.getLogger(__name__)


class LegislationBlobUploader:
    """
    Download PDFs from legislation.gov.uk and upload to Azure Blob Storage.

    Features:
    - Downloads from legislation.gov.uk
    - Uploads to Azure Blob Storage with hierarchical structure
    - Generates SAS URLs for Azure OpenAI access
    - Skips already uploaded files
    - Concurrent processing with rate limiting

    Usage:
        uploader = LegislationBlobUploader()
        results = await uploader.process_batch(pdf_urls, legislation_types, identifiers)
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        container_name: Optional[str] = None,
        max_concurrent: int = 10,
        timeout_seconds: int = 900,  # 15 minutes for large PDFs
        sas_expiry_hours: int = 720,  # 30 days
    ):
        """
        Initialize blob uploader.

        Args:
            connection_string: Azure Storage connection string (from env if not provided)
            container_name: Container name (from env if not provided)
            max_concurrent: Maximum concurrent downloads (default 10)
            timeout_seconds: HTTP timeout in seconds (default 900 = 15 minutes)
            sas_expiry_hours: SAS token expiry in hours (default 720 = 30 days)
        """
        self.connection_string = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = container_name or os.getenv(
            "AZURE_STORAGE_CONTAINER_NAME", "historical-legislation-pdfs"
        )
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.sas_expiry_hours = sas_expiry_hours

        if not self.connection_string:
            raise ValueError("Azure Storage connection string not found")

        # Initialize blob service client
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self.container_client = self.blob_service_client.get_container_client(self.container_name)

        # Extract account key for SAS generation
        self.account_name = self.blob_service_client.account_name
        self.account_key = self._extract_account_key(self.connection_string)

        logger.info(f"Azure Blob uploader initialized: {self.account_name}/{self.container_name}")

    def _extract_account_key(self, connection_string: str) -> str:
        """Extract account key from connection string."""
        for part in connection_string.split(";"):
            if part.startswith("AccountKey="):
                return part.split("=", 1)[1]
        raise ValueError("AccountKey not found in connection string")

    def get_blob_name(
        self, legislation_type: str, identifier: str, chunk_num: Optional[int] = None
    ) -> str:
        """
        Get blob name for a PDF, preserving legislation.gov.uk structure.

        Args:
            legislation_type: Type code (e.g., 'aep', 'ukla')
            identifier: Identifier (e.g., 'Ja1/7/18', 'Geo3/46/122')
            chunk_num: Optional chunk number (for split PDFs)

        Returns:
            Blob name like: aep/Ja1/7/18/pdfs/aep_Ja170018_en.pdf
            Or for chunks: aep/Ja1/7/18/pdfs/aep_Ja170018_en_chunk_001.pdf
        """
        # Generate filename from identifier
        # Convert identifier like "Ja1/7/18" to "aep_Ja170018_en"
        identifier_parts = identifier.replace("/", "")
        base_filename = f"{legislation_type}_{identifier_parts}_en"

        if chunk_num is not None:
            filename = f"{base_filename}_chunk_{chunk_num:03d}.pdf"
        else:
            filename = f"{base_filename}.pdf"

        # Build path: type/identifier/pdfs/filename
        blob_name = f"{legislation_type}/{identifier}/pdfs/{filename}"

        return blob_name

    def generate_sas_url(self, blob_name: str) -> str:
        """
        Generate SAS URL for blob with read permissions.

        Args:
            blob_name: Name of blob in container

        Returns:
            Full SAS URL for accessing the blob
        """
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=self.sas_expiry_hours),
        )

        sas_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"
        return sas_url

    async def process_pdf(
        self, session: aiohttp.ClientSession, pdf_url: str, legislation_type: str, identifier: str
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Download PDF and upload to Azure Blob Storage (or reuse existing).

        Args:
            session: aiohttp ClientSession
            pdf_url: URL to PDF on legislation.gov.uk
            legislation_type: Type code
            identifier: Identifier

        Returns:
            Tuple of (success, sas_url, blob_name, error_message)
        """
        blob_name = self.get_blob_name(legislation_type, identifier)
        blob_client = self.container_client.get_blob_client(blob_name)

        # Reuse existing blob if available (optimization)
        try:
            if blob_client.exists():
                logger.debug(f"Reusing existing blob: {blob_name}")
                sas_url = self.generate_sas_url(blob_name)
                return True, sas_url, blob_name, None
        except Exception as e:
            logger.warning(f"Error checking blob existence: {e}")

        try:
            # Download PDF from legislation.gov.uk
            # Allow redirects (http:// to https://)
            async with session.get(pdf_url, timeout=self.timeout, allow_redirects=True) as response:
                response.raise_for_status()
                pdf_bytes = await response.read()

            # Upload to Azure Blob Storage
            blob_client.upload_blob(pdf_bytes, overwrite=False)

            # Generate SAS URL
            sas_url = self.generate_sas_url(blob_name)

            logger.info(f"Uploaded: {pdf_url} -> {blob_name}")
            return True, sas_url, blob_name, None

        except asyncio.TimeoutError:
            error = f"Timeout downloading {pdf_url}"
            logger.error(error)
            return False, "", blob_name, error

        except aiohttp.ClientError as e:
            error = f"HTTP error downloading {pdf_url}: {e}"
            logger.error(error)
            return False, "", blob_name, error

        except Exception as e:
            error = f"Failed to process {pdf_url}: {e}"
            logger.error(error)
            return False, "", blob_name, error

    async def process_pdf_with_chunking(
        self,
        session: aiohttp.ClientSession,
        pdf_url: str,
        legislation_type: str,
        identifier: str,
        page_count: int,
        chunk_size_pages: int = 40,
    ) -> Union[
        Tuple[bool, str, Optional[str], Optional[str]],
        List[Tuple[bool, str, Optional[str], Optional[str], int, int]],
    ]:
        """
        Download PDF and upload to Azure Blob Storage with automatic chunking for large PDFs.

        If page_count > chunk_size_pages, splits PDF into chunks and uploads separately.
        Otherwise uploads as single PDF.

        Args:
            session: aiohttp ClientSession
            pdf_url: URL to PDF on legislation.gov.uk
            legislation_type: Type code
            identifier: Identifier
            page_count: Total number of pages in PDF
            chunk_size_pages: Maximum pages per chunk (default: 40)

        Returns:
            If single PDF: (success, sas_url, blob_name, error_message)
            If chunked: List of (success, sas_url, blob_name, error_message, start_page, end_page)
        """
        # Check if chunking is needed
        if page_count <= chunk_size_pages:
            logger.info(f"PDF has {page_count} pages (<={chunk_size_pages}), single upload")
            result = await self.process_pdf(session, pdf_url, legislation_type, identifier)
            return result

        logger.info(
            f"PDF has {page_count} pages (>{chunk_size_pages}), splitting into chunks"
        )

        try:
            # Download original PDF
            async with session.get(pdf_url, timeout=self.timeout, allow_redirects=True) as response:
                response.raise_for_status()
                pdf_bytes = await response.read()

            # Split into chunks
            chunks = split_pdf_into_chunks(pdf_bytes, chunk_size_pages)

            # Upload each chunk
            results = []
            for chunk_num, (chunk_bytes, start_page, end_page) in enumerate(chunks, 1):
                # Generate blob name for this chunk
                blob_name = self.get_blob_name(legislation_type, identifier, chunk_num=chunk_num)
                blob_client = self.container_client.get_blob_client(blob_name)

                # Check if chunk already exists
                try:
                    if blob_client.exists():
                        logger.debug(f"Reusing existing chunk blob: {blob_name}")
                        sas_url = self.generate_sas_url(blob_name)
                        results.append((True, sas_url, blob_name, None, start_page, end_page))
                        continue
                except Exception as e:
                    logger.warning(f"Error checking chunk blob existence: {e}")

                # Upload chunk
                blob_client.upload_blob(chunk_bytes, overwrite=False)

                # Generate SAS URL
                sas_url = self.generate_sas_url(blob_name)

                results.append((True, sas_url, blob_name, None, start_page, end_page))

                logger.info(
                    f"Uploaded chunk {chunk_num}/{len(chunks)}: {blob_name} "
                    f"(pages {start_page+1}-{end_page}, {len(chunk_bytes) / 1024:.1f}KB)"
                )

            return results

        except asyncio.TimeoutError:
            error = f"Timeout downloading {pdf_url}"
            logger.error(error)
            return [(False, "", "", error, 0, 0)]

        except aiohttp.ClientError as e:
            error = f"HTTP error downloading {pdf_url}: {e}"
            logger.error(error)
            return [(False, "", "", error, 0, 0)]

        except Exception as e:
            error = f"Failed to process chunked PDF {pdf_url}: {e}"
            logger.error(error)
            return [(False, "", "", error, 0, 0)]

    async def process_batch(
        self,
        pdf_urls: List[str],
        legislation_types: List[str],
        identifiers: List[str],
        show_progress: bool = True,
    ) -> List[Tuple[bool, str, Optional[str], Optional[str]]]:
        """
        Process multiple PDFs concurrently: download + upload + generate SAS URLs.

        Args:
            pdf_urls: List of PDF URLs from legislation.gov.uk
            legislation_types: List of legislation types (parallel to pdf_urls)
            identifiers: List of identifiers (parallel to pdf_urls)
            show_progress: Show progress bar

        Returns:
            List of (success, sas_url, blob_name, error_message) tuples
        """
        if not (len(pdf_urls) == len(legislation_types) == len(identifiers)):
            raise ValueError("pdf_urls, legislation_types, and identifiers must have same length")

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_with_semaphore(
            session: aiohttp.ClientSession, url: str, leg_type: str, ident: str
        ) -> Tuple[bool, str, Optional[str], Optional[str]]:
            async with semaphore:
                return await self.process_pdf(session, url, leg_type, ident)

        # Create HTTP session
        async with aiohttp.ClientSession() as session:
            # Create tasks
            tasks = [
                process_with_semaphore(session, url, leg_type, ident)
                for url, leg_type, ident in zip(pdf_urls, legislation_types, identifiers)
            ]

            # Execute with progress bar
            if show_progress:
                results = []
                for task in tqdm(
                    asyncio.as_completed(tasks), total=len(tasks), desc="Processing PDFs"
                ):
                    result = await task
                    results.append(result)
            else:
                results = await asyncio.gather(*tasks)

        # Log summary
        successful = sum(1 for success, _, _, _ in results if success)
        failed = len(results) - successful
        logger.info(f"Batch complete: {successful}/{len(results)} successful, {failed} failed")

        return results
