"""
PDF processor for historical UK legislation using Azure OpenAI Responses API.

This module handles OCR and structured extraction from scanned historical legislation PDFs
using GPT-5-mini vision capabilities with Langfuse tracing for observability.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from langfuse import Langfuse, observe
from openai import AsyncAzureOpenAI, RateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from lex.processing.historical_pdf.models import ExtractionProvenance, ExtractionResult, LegislationMetadata

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 5
BASE_BACKOFF = 1.0

# Timeout configuration (generous for 40+ page PDFs)
API_TIMEOUT_SECONDS = 900  # 15 minutes for API calls
PROMPT_VERSION = "1.1"  # For provenance tracking (v1.1: Added ISO 8601 date format specification)


class LegislationPDFProcessor:
    """
    Process historical UK legislation PDFs using Azure OpenAI Responses API.

    Features:
    - Native PDF processing with GPT-5-mini vision
    - Multi-page document support with context preservation
    - Langfuse tracing for observability
    - Automatic retry logic for rate limits
    - Prompt caching optimization

    Usage:
        processor = LegislationPDFProcessor()
        result = await processor.process_pdf(Path("legislation.pdf"))
    """

    def __init__(
        self,
        azure_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-5-mini",
        langfuse_public_key: Optional[str] = None,
        langfuse_secret_key: Optional[str] = None,
        langfuse_host: Optional[str] = None,
    ):
        """
        Initialize PDF processor with Azure OpenAI and Langfuse.

        Args:
            azure_endpoint: Azure OpenAI endpoint (from env if not provided)
            api_key: Azure OpenAI API key (from env if not provided)
            model: Model to use (default: gpt-5-mini)
            langfuse_public_key: Langfuse public key (from env if not provided)
            langfuse_secret_key: Langfuse secret key (from env if not provided)
            langfuse_host: Langfuse host URL (from env if not provided)
        """
        # Azure OpenAI setup
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.model = model

        if not self.azure_endpoint or not self.api_key:
            raise ValueError(
                "Azure OpenAI credentials missing. Set AZURE_OPENAI_ENDPOINT "
                "and AZURE_OPENAI_API_KEY environment variables."
            )

        # Initialize async Azure OpenAI client with generous timeout
        self.client = AsyncAzureOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.api_key,
            api_version="2025-03-01-preview",  # Responses API requires 2025-03-01-preview or later
            max_retries=0,  # We handle retries manually
            timeout=API_TIMEOUT_SECONDS,  # 15 minutes for large PDFs
        )

        # Langfuse setup
        langfuse_public = langfuse_public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        langfuse_secret = langfuse_secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        langfuse_host_url = langfuse_host or os.getenv(
            "LANGFUSE_HOST", "https://cloud.langfuse.com"
        )

        if langfuse_public and langfuse_secret:
            self.langfuse = Langfuse(
                public_key=langfuse_public, secret_key=langfuse_secret, host=langfuse_host_url
            )
            logger.info("Langfuse tracing enabled")
        else:
            self.langfuse = None
            logger.warning(
                "Langfuse credentials missing. Set LANGFUSE_PUBLIC_KEY and "
                "LANGFUSE_SECRET_KEY for tracing support."
            )

        # Extraction prompt (>1024 tokens for caching)
        self.extraction_prompt = """
You are an expert at extracting structured text from historical UK legislation documents (1267-1962).

Your task is to:
1. Perform OCR on the scanned document pages
2. Extract all text content accurately
3. Preserve document structure (sections, subsections, schedules)
4. Handle historical typography (long-s character: ſ → s)
5. Output structured JSON

OUTPUT FORMAT (JSON):
{
    "metadata": {
        "title": "Full Act title",
        "reference": "Document reference (e.g., 'ukpga/Geo3/41/90')",
        "date_enacted": "Date in ISO 8601 format YYYY-MM-DD (e.g., '1798-04-05' for 5th April 1798)",
        "monarch": "Monarch name (e.g., 'George III')",
        "regnal_year": "Regnal year (e.g., 'Anno Tricesimo Octavo')",
        "chapter_number": "Chapter number (e.g., 'Cap. 16')"
    },
    "preamble": "WHEREAS clause text (if present)",
    "sections": [
        {
            "number": "I" or "1",
            "heading": "Section heading or marginal note",
            "text": "Full section text"
        }
    ],
    "schedules": [
        {
            "number": "1" or "First",
            "title": "Schedule title",
            "text": "Schedule content"
        }
    ]
}

IMPORTANT RULES:
1. Convert long-s (ſ) to regular "s" (e.g., "Succeſſors" → "Successors")
2. Preserve original spelling, capitalization, and punctuation otherwise
3. Include ALL sections and schedules
4. For marginal notes, include them as "heading"
5. If text is illegible, mark as "[ILLEGIBLE]"
6. If uncertain, mark as "[UNCLEAR: possible_text]"
7. Maintain section numbering exactly as in document (Roman or Arabic numerals)

Handle document quality issues:
- Foxing (brown spots): ignore, extract text
- Faded text: do your best OCR
- Edge degradation: extract visible portions
- Multi-column layouts: read left column top-to-bottom, then right column
"""

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=BASE_BACKOFF, min=BASE_BACKOFF, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _make_responses_request(
        self, pdf_url: str, prompt: Optional[str] = None, previous_response_id: Optional[str] = None
    ) -> Dict:
        """
        Make a request to Azure OpenAI Responses API with retry logic.

        Args:
            pdf_url: URL to PDF file (from legislation.gov.uk)
            prompt: Custom prompt (uses default extraction_prompt if not provided)
            previous_response_id: Response ID for continuation (maintains context)

        Returns:
            Response dictionary with id, output, and usage
        """
        # Build request content using direct URL
        content = [
            {"type": "input_text", "text": prompt or self.extraction_prompt},
            {"type": "input_file", "file_url": pdf_url},
        ]

        # Build request parameters
        request_params = {"model": self.model, "input": [{"role": "user", "content": content}]}

        # Add previous_response_id for context continuation
        if previous_response_id:
            request_params["previous_response_id"] = previous_response_id

        # Make API call
        response = await self.client.responses.create(**request_params)

        # Extract text from response output
        # Response structure with reasoning (GPT-5-mini default):
        #   response.output[0] = ResponseReasoningItem (type='reasoning')
        #   response.output[1] = ResponseOutputMessage (type='message') with content
        # Response structure without reasoning:
        #   response.output[0] = ResponseOutputMessage (type='message') with content
        output_text = ""
        if response.output and len(response.output) > 0:
            # Find the message item (skip reasoning items)
            message_item = None
            for item in response.output:
                item_type = getattr(item, "type", None)
                if item_type == "message":
                    message_item = item
                    break

            if message_item:
                # Extract text from message content
                if hasattr(message_item, "content") and message_item.content:
                    for content_part in message_item.content:
                        if hasattr(content_part, "type") and content_part.type == "output_text":
                            if hasattr(content_part, "text") and content_part.text:
                                output_text += content_part.text

                    logger.info(f"Extracted {len(output_text)} chars from message content")
                else:
                    logger.warning("Message item has no content")
            else:
                logger.warning(
                    f"No message item found in response.output (only found: {[getattr(item, 'type', 'unknown') for item in response.output]})"
                )

        return {
            "id": response.id,
            "output": output_text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cached_tokens": getattr(response.usage, "cached_tokens", 0),
            },
        }

    @observe(as_type="generation", capture_input=True, capture_output=True)
    async def process_pdf(
        self,
        pdf_url: str,
        legislation_type: Optional[str] = None,
        identifier: Optional[str] = None,
        metadata: Optional[LegislationMetadata] = None,
        trace_name: Optional[str] = None,
        max_pages_single_shot: int = 45,
    ) -> ExtractionResult:
        """
        Process a PDF using Azure OpenAI Responses API with adaptive chunking.

        This method handles:
        - Direct URL access to PDFs (from legislation.gov.uk)
        - Single or multi-page PDFs
        - **Automatic chunking for PDFs >45 pages** (adaptive routing)
        - Automatic retries for rate limits
        - Langfuse tracing
        - Context preservation for large documents via previous_response_id
        - Metadata enrichment of OCR prompt

        Args:
            pdf_url: URL to PDF file (e.g., from legislation.gov.uk)
            legislation_type: Optional legislation type (e.g., 'ukpga', 'ukla')
            identifier: Optional identifier (e.g., 'Geo3/46/122')
            metadata: Optional metadata from legislation.gov.uk XML
            trace_name: Optional name for Langfuse trace
            max_pages_single_shot: Maximum pages for single-shot processing (default: 45)

        Returns:
            ExtractionResult with extracted data and provenance
        """
        start_time = time.time()

        # Note: Chunking for large PDFs happens at blob upload stage
        # The blob uploader splits PDFs and passes chunk URLs to this method
        # This method receives either a single SAS URL or is called via process_large_pdf_chunked()

        try:
            logger.info(f"Processing PDF from URL: {pdf_url}")

            # Build prompt with metadata if provided
            prompt = self.extraction_prompt
            if metadata:
                context = metadata.to_prompt_context()
                if context:
                    prompt = f"""KNOWN METADATA FROM legislation.gov.uk:
{context}

{self.extraction_prompt}"""
                    logger.info(f"Enhanced prompt with metadata: {len(context)} chars")

            # Update Langfuse trace if enabled
            if self.langfuse:
                # Update current trace with metadata
                self.langfuse.update_current_trace(
                    name=trace_name
                    or f"pdf_processing_{legislation_type or 'unknown'}_{identifier or 'unknown'}",
                    metadata={
                        "pdf_url": pdf_url,
                        "legislation_type": legislation_type,
                        "identifier": identifier,
                        "model": self.model,
                    },
                )

                # Update current span (generation) with input
                self.langfuse.update_current_span(
                    input={"prompt_length": len(self.extraction_prompt), "pdf_url": pdf_url}
                )

            # Make API request with enhanced prompt
            response = await self._make_responses_request(pdf_url, prompt=prompt)

            # Calculate metrics
            processing_time = time.time() - start_time

            # Build result with provenance
            result = ExtractionResult(
                extracted_data=response["output"],
                provenance=ExtractionProvenance(
                    model=self.model,
                    prompt_version=PROMPT_VERSION,
                    timestamp=datetime.utcnow(),
                    processing_time_seconds=processing_time,
                    input_tokens=response["usage"]["input_tokens"],
                    output_tokens=response["usage"]["output_tokens"],
                    cached_tokens=response["usage"]["cached_tokens"],
                    response_id=response["id"],
                ),
                success=True,
                pdf_source=pdf_url,
                legislation_type=legislation_type,
                identifier=identifier,
            )

            # Update Langfuse with results
            if self.langfuse:
                self.langfuse.update_current_span(
                    output={
                        "extracted_json_length": len(response["output"]),
                        "extracted_json_preview": response["output"][:500] + "..."
                        if len(response["output"]) > 500
                        else response["output"],
                    },
                    metadata={
                        "response_id": response["id"],
                        "input_tokens": response["usage"]["input_tokens"],
                        "output_tokens": response["usage"]["output_tokens"],
                        "cached_tokens": response["usage"]["cached_tokens"],
                        "processing_time_seconds": round(processing_time, 2),
                    },
                )

            logger.info(
                f"PDF processed: {pdf_url} - "
                f"{result.provenance.input_tokens} input tokens, "
                f"{result.provenance.output_tokens} output tokens, "
                f"{result.provenance.cached_tokens} cached tokens, "
                f"{processing_time:.2f}s"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Failed to process PDF {pdf_url}: {e}", exc_info=True)

            return ExtractionResult(
                extracted_data="",
                provenance=ExtractionProvenance(
                    model=self.model,
                    prompt_version=PROMPT_VERSION,
                    timestamp=datetime.utcnow(),
                    processing_time_seconds=processing_time,
                    input_tokens=0,
                    output_tokens=0,
                    cached_tokens=0,
                    response_id="",
                ),
                success=False,
                error=str(e),
                pdf_source=pdf_url,
                legislation_type=legislation_type,
                identifier=identifier,
            )

    async def process_pdf_batch(
        self,
        pdf_urls: List[str],
        legislation_types: Optional[List[str]] = None,
        identifiers: Optional[List[str]] = None,
        max_concurrent: int = 10,
        progress_callback: Optional[callable] = None,
    ) -> List[ExtractionResult]:
        """
        Process multiple PDFs concurrently.

        Args:
            pdf_urls: List of PDF URLs (from legislation.gov.uk)
            legislation_types: Optional list of legislation types (parallel to pdf_urls)
            identifiers: Optional list of identifiers (parallel to pdf_urls)
            max_concurrent: Maximum concurrent requests (default 10)
            progress_callback: Optional callback(completed, total) for progress

        Returns:
            List of ExtractionResults in same order as input
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        completed = 0
        total = len(pdf_urls)

        async def process_with_semaphore(idx: int, url: str) -> ExtractionResult:
            nonlocal completed
            async with semaphore:
                result = await self.process_pdf(
                    pdf_url=url,
                    legislation_type=legislation_types[idx] if legislation_types else None,
                    identifier=identifiers[idx] if identifiers else None,
                )
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
                return result

        logger.info(f"Processing {total} PDFs with max {max_concurrent} concurrent requests")

        tasks = [process_with_semaphore(i, url) for i, url in enumerate(pdf_urls)]
        results = await asyncio.gather(*tasks)

        # Log summary
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        total_input_tokens = sum(r.provenance.input_tokens for r in results)
        total_output_tokens = sum(r.provenance.output_tokens for r in results)
        total_cached_tokens = sum(r.provenance.cached_tokens for r in results)

        logger.info(
            f"Batch complete: {successful}/{total} successful, {failed} failed - "
            f"Total tokens: {total_input_tokens} input, {total_output_tokens} output, "
            f"{total_cached_tokens} cached"
        )

        return results

    async def process_large_pdf_chunked(
        self,
        chunk_urls: List[Tuple[str, int, int]],
        legislation_type: Optional[str] = None,
        identifier: Optional[str] = None,
        metadata: Optional[LegislationMetadata] = None,
    ) -> ExtractionResult:
        """
        Process large PDF using pre-split chunks from blob storage.

        Each chunk is a separate PDF blob with its own SAS URL.
        Uses previous_response_id to maintain context across chunks.

        Args:
            chunk_urls: List of (chunk_sas_url, start_page, end_page) tuples
            legislation_type: Optional legislation type
            identifier: Optional identifier
            metadata: Optional metadata from legislation.gov.uk XML

        Returns:
            ExtractionResult with merged sections from all chunks
        """
        start_time = time.time()
        total_pages = chunk_urls[-1][2] if chunk_urls else 0
        logger.info(f"Processing {len(chunk_urls)} pre-split PDF chunks ({total_pages} total pages)")

        # Process each chunk with context continuation
        chunk_results = []
        previous_response_id = None

        for chunk_num, (chunk_url, start_page, end_page) in enumerate(chunk_urls, 1):
            try:
                # Build chunk-specific prompt
                base_prompt = self.extraction_prompt

                # Add metadata context if available
                if metadata:
                    context = metadata.to_prompt_context()
                    if context:
                        base_prompt = f"""KNOWN METADATA FROM legislation.gov.uk:
{context}

{base_prompt}"""

                # Add chunking instructions
                is_first_chunk = chunk_num == 1
                chunk_prompt = f"""
{base_prompt}

**CHUNKING INSTRUCTIONS - IMPORTANT:**
- This is PART {chunk_num} of {len(chunk_urls)} (pages {start_page+1}-{end_page} of {total_pages} total)
- {"This is the FIRST chunk: Extract metadata, preamble, and sections from these pages." if is_first_chunk else "CONTINUE from previous chunk: Maintain section numbering continuity. Only extract new sections from these pages."}
- Ensure section numbers continue sequentially from previous chunk
"""

                logger.info(f"Processing chunk {chunk_num}/{len(chunk_urls)} (pages {start_page+1}-{end_page})")

                # Make API request with continuation
                # Each chunk has its own URL → no image accumulation!
                response = await self._make_responses_request(
                    pdf_url=chunk_url,
                    prompt=chunk_prompt,
                    previous_response_id=previous_response_id
                )

                chunk_results.append({
                    "chunk_num": chunk_num,
                    "start_page": start_page,
                    "end_page": end_page,
                    "response": response,
                })

                # Chain for next chunk
                previous_response_id = response["id"]

                logger.info(
                    f"Chunk {chunk_num} complete: {response['usage']['input_tokens']} input tokens, "
                    f"{response['usage']['output_tokens']} output tokens"
                )

            except Exception as e:
                logger.error(f"Failed to process chunk {chunk_num} (pages {start_page+1}-{end_page}): {e}")
                raise

        # Merge chunk results
        try:
            merged_result = self._merge_chunk_results(
                chunks=chunk_results,
                pdf_url=chunk_urls[0][0],  # Use first chunk URL as reference
                legislation_type=legislation_type,
                identifier=identifier,
                page_count=total_pages,
                total_time=time.time() - start_time,
            )

            logger.info(
                f"Large PDF processing complete: {total_pages} pages in {len(chunk_urls)} chunks - "
                f"{merged_result.provenance.input_tokens} total input tokens, "
                f"{merged_result.provenance.output_tokens} total output tokens"
            )

            return merged_result

        except Exception as e:
            logger.error(f"Failed to merge chunk results: {e}")
            raise

    def _merge_chunk_results(
        self,
        chunks: List[Dict],
        pdf_url: str,
        legislation_type: Optional[str],
        identifier: Optional[str],
        page_count: int,
        total_time: float,
    ) -> ExtractionResult:
        """
        Merge JSON from multiple chunks into single ExtractionResult.

        Args:
            chunks: List of chunk result dicts with response data
            pdf_url: PDF source URL
            legislation_type: Legislation type
            identifier: Identifier
            page_count: Total page count
            total_time: Total processing time

        Returns:
            Merged ExtractionResult
        """
        import json

        logger.info(f"Merging {len(chunks)} chunk results")

        # Parse first chunk for metadata/preamble
        first_chunk_data = json.loads(chunks[0]["response"]["output"])

        merged = {
            "metadata": first_chunk_data.get("metadata", {}),
            "preamble": first_chunk_data.get("preamble", ""),
            "sections": [],
            "schedules": []
        }

        # Concatenate sections and schedules from all chunks
        for chunk in chunks:
            try:
                chunk_data = json.loads(chunk["response"]["output"])

            except json.JSONDecodeError as e:
                # Try to recover if there's "extra data" after valid JSON
                if "Extra data" in str(e):
                    try:
                        # Use JSONDecoder to get first complete object
                        decoder = json.JSONDecoder()
                        chunk_data, _ = decoder.raw_decode(chunk["response"]["output"])
                        logger.warning(
                            f"Chunk {chunk['chunk_num']} had extra data after JSON, recovered first object"
                        )
                    except Exception as e2:
                        logger.error(f"Failed to parse chunk {chunk['chunk_num']} JSON even after recovery: {e2}")
                        continue
                else:
                    logger.error(f"Failed to parse chunk {chunk['chunk_num']} JSON: {e}")
                    continue

            # Add sections from this chunk
            chunk_sections = chunk_data.get("sections", [])
            merged["sections"].extend(chunk_sections)

            # Add schedules from this chunk
            chunk_schedules = chunk_data.get("schedules", [])
            merged["schedules"].extend(chunk_schedules)

            logger.debug(
                f"Chunk {chunk['chunk_num']}: {len(chunk_sections)} sections, "
                f"{len(chunk_schedules)} schedules"
            )

        # Aggregate token usage and provenance
        total_input_tokens = sum(c["response"]["usage"]["input_tokens"] for c in chunks)
        total_output_tokens = sum(c["response"]["usage"]["output_tokens"] for c in chunks)
        total_cached_tokens = sum(c["response"]["usage"]["cached_tokens"] for c in chunks)

        # Use last chunk's response ID as primary reference
        final_response_id = chunks[-1]["response"]["id"]

        # Build provenance with chunking metadata
        provenance = ExtractionProvenance(
            model=self.model,
            prompt_version=f"{PROMPT_VERSION}_chunked_{len(chunks)}",
            timestamp=datetime.utcnow(),
            processing_time_seconds=total_time,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cached_tokens=total_cached_tokens,
            response_id=final_response_id,
        )

        logger.info(
            f"Merged {len(merged['sections'])} sections and {len(merged['schedules'])} schedules "
            f"from {len(chunks)} chunks"
        )

        # Basic validation: warn about potential section numbering issues
        if merged["sections"]:
            section_numbers = []
            for section in merged["sections"]:
                num = section.get("number", "")
                # Try to extract numeric part (handles "1", "I", "1A", etc.)
                if num and num[0].isdigit():
                    try:
                        section_numbers.append(int(num.split()[0]))
                    except (ValueError, IndexError):
                        pass

            if section_numbers and len(section_numbers) > 1:
                # Check if roughly sequential (allow some gaps for schedules/appendices)
                expected = list(range(1, len(section_numbers) + 1))
                if section_numbers != expected:
                    logger.warning(
                        f"Section numbering may have gaps: found {len(section_numbers)} numeric sections, "
                        f"first={section_numbers[0]}, last={section_numbers[-1]}"
                    )

        return ExtractionResult(
            extracted_data=json.dumps(merged, indent=2),
            provenance=provenance,
            success=True,
            pdf_source=pdf_url,
            legislation_type=legislation_type,
            identifier=identifier,
        )

    async def close(self):
        """Close the Azure OpenAI client and flush Langfuse traces."""
        await self.client.close()
        if self.langfuse:
            self.langfuse.flush()
            logger.info("Langfuse traces flushed")


# Convenience async functions for single-use
async def process_single_pdf_url(
    pdf_url: str, legislation_type: Optional[str] = None, identifier: Optional[str] = None
) -> ExtractionResult:
    """
    Process a single PDF from URL (convenience function).

    Args:
        pdf_url: URL to PDF file
        legislation_type: Optional legislation type
        identifier: Optional identifier

    Returns:
        ExtractionResult
    """
    processor = LegislationPDFProcessor()
    try:
        return await processor.process_pdf(pdf_url, legislation_type, identifier)
    finally:
        await processor.close()


async def process_pdf_batch_from_urls(
    pdf_urls: List[str],
    legislation_types: Optional[List[str]] = None,
    identifiers: Optional[List[str]] = None,
    max_concurrent: int = 10,
) -> List[ExtractionResult]:
    """
    Process multiple PDFs from URLs (convenience function).

    Args:
        pdf_urls: List of PDF URLs
        legislation_types: Optional list of legislation types
        identifiers: Optional list of identifiers
        max_concurrent: Maximum concurrent requests

    Returns:
        List of ExtractionResults
    """
    processor = LegislationPDFProcessor()
    try:
        return await processor.process_pdf_batch(
            pdf_urls, legislation_types, identifiers, max_concurrent
        )
    finally:
        await processor.close()
