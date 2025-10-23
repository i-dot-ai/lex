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
from typing import Dict, List, Optional

from langfuse import Langfuse, observe
from openai import AsyncAzureOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from lex.pdf_digitization.models import (
    ExtractionResult,
    ExtractionProvenance,
    LegislationMetadata,
)

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
                    logger.warning(f"Message item has no content")
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
    ) -> ExtractionResult:
        """
        Process a PDF using Azure OpenAI Responses API.

        This method handles:
        - Direct URL access to PDFs (from legislation.gov.uk)
        - Single or multi-page PDFs
        - Automatic retries for rate limits
        - Langfuse tracing
        - Context preservation for large documents
        - Metadata enrichment of OCR prompt

        Args:
            pdf_url: URL to PDF file (e.g., from legislation.gov.uk)
            legislation_type: Optional legislation type (e.g., 'ukpga', 'ukla')
            identifier: Optional identifier (e.g., 'Geo3/46/122')
            metadata: Optional metadata from legislation.gov.uk XML
            trace_name: Optional name for Langfuse trace

        Returns:
            ExtractionResult with extracted data and provenance
        """
        start_time = time.time()

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
