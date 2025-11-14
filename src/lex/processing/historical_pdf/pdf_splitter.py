"""
PDF splitting utility for chunking large documents.

Uses pypdf to extract specific page ranges into separate PDF files.
"""

import logging
from io import BytesIO
from typing import List, Tuple

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def split_pdf_into_chunks(
    pdf_bytes: bytes, chunk_size_pages: int = 40
) -> List[Tuple[bytes, int, int]]:
    """
    Split PDF into chunks of specified page size.

    Args:
        pdf_bytes: Original PDF as bytes
        chunk_size_pages: Maximum pages per chunk (default: 40)

    Returns:
        List of (chunk_pdf_bytes, start_page, end_page) tuples
        where start_page is 0-indexed and end_page is exclusive

    Example:
        >>> chunks = split_pdf_into_chunks(pdf_bytes, chunk_size_pages=10)
        >>> for chunk_bytes, start, end in chunks:
        ...     print(f"Chunk: pages {start+1}-{end}")
        Chunk: pages 1-10
        Chunk: pages 11-20
        Chunk: pages 21-24
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    total_pages = len(reader.pages)

    logger.info(
        f"Splitting {total_pages}-page PDF into chunks of {chunk_size_pages} pages"
    )

    chunks = []

    for chunk_start in range(0, total_pages, chunk_size_pages):
        chunk_end = min(chunk_start + chunk_size_pages, total_pages)

        # Create new PDF with only this chunk's pages
        writer = PdfWriter()
        for page_num in range(chunk_start, chunk_end):
            writer.add_page(reader.pages[page_num])

        # Write to BytesIO buffer
        chunk_buffer = BytesIO()
        writer.write(chunk_buffer)
        chunk_buffer.seek(0)
        chunk_bytes = chunk_buffer.getvalue()

        chunks.append((chunk_bytes, chunk_start, chunk_end))

        logger.debug(
            f"Created chunk {len(chunks)}: pages {chunk_start+1}-{chunk_end} "
            f"({len(chunk_bytes) / 1024:.1f}KB)"
        )

    logger.info(f"Split into {len(chunks)} chunks")
    return chunks
