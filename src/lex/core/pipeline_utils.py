"""Pipeline utilities for cross-cutting concerns like monitoring, logging, and checkpointing."""

import logging
import re
import time
from functools import wraps
from typing import Any, Callable, Dict, Iterator, Type, TypeVar

from lex.core.document import generate_documents
from lex.core.models import LexModel

T = TypeVar("T", bound=LexModel)


class PipelineMonitor:
    """Decorator for pipeline monitoring and structured logging.

    This decorator adds consistent logging and performance monitoring
    to pipeline functions without cluttering the business logic.
    """

    def __init__(self, doc_type: str, track_progress: bool = True, progress_interval: int = 10):
        """Initialize the pipeline monitor.

        Args:
            doc_type: The type of document being processed (e.g., 'legislation', 'caselaw')
            track_progress: Whether to log progress updates
            progress_interval: Seconds between progress updates
        """
        self.doc_type = doc_type
        self.track_progress = track_progress
        self.progress_interval = progress_interval

    def __call__(self, func: Callable[..., Iterator[T]]) -> Callable[..., Iterator[T]]:
        """Wrap the pipeline function with monitoring capabilities."""

        @wraps(func)
        def wrapper(*args, **kwargs) -> Iterator[T]:
            logger = logging.getLogger(func.__module__)
            start_time = time.time()
            doc_count = 0
            last_progress_time = start_time

            # Extract meaningful parameters for logging
            params_info = self._extract_params_info(args, kwargs)

            logger.info(
                f"Starting {self.doc_type} pipeline",
                extra={"doc_type": self.doc_type, "pipeline_status": "started", **params_info},
            )

            try:
                for doc in func(*args, **kwargs):
                    doc_count += 1

                    # Log successful processing with document metadata
                    doc_metadata = self._extract_doc_metadata(doc)

                    logger.info(
                        f"Processed {self.doc_type} document: {doc.id}",
                        extra={
                            "doc_type": self.doc_type,
                            "processing_status": "success",
                            "doc_count": doc_count,
                            **doc_metadata,
                        },
                    )

                    # Progress tracking
                    if self.track_progress:
                        current_time = time.time()
                        if current_time - last_progress_time >= self.progress_interval:
                            elapsed = current_time - start_time
                            rate = doc_count / elapsed if elapsed > 0 else 0

                            logger.info(
                                f"Pipeline progress: {doc_count} documents processed",
                                extra={
                                    "doc_type": self.doc_type,
                                    "pipeline_status": "in_progress",
                                    "doc_count": doc_count,
                                    "elapsed_seconds": elapsed,
                                    "docs_per_second": rate,
                                },
                            )
                            last_progress_time = current_time

                    yield doc

            except Exception as e:
                # Pipeline-level error - log and re-raise
                logger.error(
                    f"Pipeline failure in {self.doc_type}: {str(e)}",
                    exc_info=True,
                    extra={
                        "doc_type": self.doc_type,
                        "pipeline_status": "failed",
                        "error_type": type(e).__name__,
                    },
                )
                raise

            finally:
                # Final summary
                elapsed = time.time() - start_time
                rate = doc_count / elapsed if elapsed > 0 else 0

                logger.info(
                    f"Completed {self.doc_type} pipeline: {doc_count} documents in {elapsed:.2f}s",
                    extra={
                        "doc_type": self.doc_type,
                        "pipeline_status": "completed",
                        "total_docs": doc_count,
                        "elapsed_seconds": elapsed,
                        "docs_per_second": rate,
                        **params_info,
                    },
                )

        return wrapper

    def _extract_params_info(self, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """Extract relevant parameters for logging."""
        info = {}

        # Common parameters across pipelines
        if "years" in kwargs:
            info["years"] = kwargs["years"]
        elif len(args) > 1 and isinstance(args[1], list):
            info["years"] = args[1]

        if "types" in kwargs:
            info["types"] = kwargs["types"]
        elif len(args) > 0 and isinstance(args[0], list):
            info["types"] = args[0]

        if "limit" in kwargs:
            info["limit"] = kwargs["limit"]

        return info

    def _extract_doc_metadata(self, doc: T) -> Dict[str, Any]:
        """Extract metadata from a document for logging."""
        metadata = {}

        # Common fields across document types
        if hasattr(doc, "id"):
            metadata["doc_id"] = doc.id

            # Try to extract year and type from ID
            year_match = re.search(r"/(\d{4})/", str(doc.id))
            if year_match:
                metadata["doc_year"] = int(year_match.group(1))

            type_match = re.search(r"/([a-z]+)/", str(doc.id))
            if type_match:
                metadata["doc_subtype"] = type_match.group(1)

        if hasattr(doc, "title"):
            metadata["doc_title"] = doc.title[:100]  # Truncate long titles

        return metadata


from lex.core.checkpoint import CheckpointCombination
from lex.core.loader import LexLoader
from lex.core.parser import LexParser


def process_checkpoints(
    checkpoints: list[CheckpointCombination],
    loader_or_scraper: LexLoader,
    parser: LexParser,
    document_type: Type[LexModel],
    limit: int,
    wrap_result: bool = False,
) -> Iterator[LexModel]:
    """Abstract common checkpoint processing logic.

    Args:
        checkpoints: List of checkpoints to process
        loader_or_scraper: Content loader or scraper instance
        parser: Parser instance with parse_content method
        document_type: The document model class to generate
        limit: Processing limit
        wrap_result: Whether to wrap the parser result in a list before passing to generate_documents

    Yields:
        Processed documents of the specified type
    """
    logger = logging.getLogger(__name__)

    remaining_limit = limit if limit is not None else float("inf")

    for checkpoint in checkpoints:
        with checkpoint as ctx:
            # Handle different load_content signatures based on whether doc_type exists
            if hasattr(checkpoint, "doc_type") and checkpoint.doc_type is not None:
                # For pipelines with types (legislation, caselaw, explanatory_note)
                # Pass None for limit if we want all documents
                passed_limit = None if limit is None else int(remaining_limit)
                content_iterator = loader_or_scraper.load_content(
                    years=[checkpoint.year], types=[checkpoint.doc_type], limit=passed_limit
                )
            else:
                # For pipelines without types (amendment)
                passed_limit = None if limit is None else int(remaining_limit)
                content_iterator = loader_or_scraper.load_content(
                    [checkpoint.year], limit=passed_limit
                )

            for url, soup in content_iterator:
                if remaining_limit <= 0:
                    logger.info("Document limit reached during processing")
                    ctx.mark_limit_hit()
                    return

                result = ctx.process_item(url, lambda: parser.parse_content(soup))
                if result:
                    remaining_limit -= 1
                    # Handle the difference between single results and lists
                    data_to_process = [result] if wrap_result else result
                    yield from generate_documents(data_to_process, document_type)


def process_checkpoints_with_combined_scraper_parser(
    checkpoints: list[CheckpointCombination],
    scraper_parser: Any,
    document_type: Type[LexModel],
    limit: int,
    wrap_result: bool = False,
) -> Iterator[LexModel]:
    """Abstract checkpoint processing for combined scraper-parser classes.

    This function handles pipelines where scraping and parsing are combined
    into a single class (like ExplanatoryNoteScraperAndParser).

    Args:
        checkpoints: List of checkpoints to process
        scraper_parser: Combined scraper-parser instance with scrape_and_parse_content method
        document_type: The document model class to generate
        limit: Processing limit (modified in place)
        wrap_result: Whether to wrap the result in a list before passing to generate_documents

    Yields:
        Processed documents of the specified type
    """
    logger = logging.getLogger(__name__)

    limit = limit if limit is not None else float("inf")

    for checkpoint in checkpoints:
        with checkpoint as ctx:
            # Handle different scrape_and_parse_content signatures based on whether doc_type exists
            if hasattr(checkpoint, "doc_type") and checkpoint.doc_type is not None:
                # For pipelines with types (explanatory_note)
                content_iterator = scraper_parser.scrape_and_parse_content(
                    [checkpoint.year], [checkpoint.doc_type]
                )
            else:
                # For pipelines without types (if any future ones exist)
                content_iterator = scraper_parser.scrape_and_parse_content([checkpoint.year])

            for url, parsed_content in content_iterator:
                if limit <= 0:
                    logger.info("Document limit reached during processing")
                    ctx.mark_limit_hit()
                    break

                # Content is already parsed, so we just pass it through
                result = ctx.process_item(url, lambda: parsed_content)
                if result:
                    limit -= 1
                    # Handle the difference between single results and lists
                    data_to_process = [result] if wrap_result else result
                    yield from generate_documents(data_to_process, document_type)
