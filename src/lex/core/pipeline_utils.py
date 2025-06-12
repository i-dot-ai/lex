"""Pipeline utilities for cross-cutting concerns like monitoring, logging, and checkpointing."""

import logging
import re
import time
from functools import wraps
from typing import Any, Callable, Dict, Iterator, TypeVar

from lex.core.models import LexModel

T = TypeVar('T', bound=LexModel)


class PipelineMonitor:
    """Decorator for pipeline monitoring and structured logging.
    
    This decorator adds consistent logging, error handling, and performance
    monitoring to pipeline functions without cluttering the business logic.
    """

    def __init__(self, doc_type: str, track_progress: bool = True,
                 progress_interval: int = 10):
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
            error_count = 0
            pdf_fallback_count = 0
            last_progress_time = start_time

            # Extract meaningful parameters for logging
            params_info = self._extract_params_info(args, kwargs)

            logger.info(
                f"Starting {self.doc_type} pipeline",
                extra={
                    "doc_type": self.doc_type,
                    "pipeline_status": "started",
                    **params_info
                }
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
                            **doc_metadata
                        }
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
                                    "error_count": error_count,
                                    "pdf_fallback_count": pdf_fallback_count
                                }
                            )
                            last_progress_time = current_time

                    yield doc

            except Exception as e:
                error_count += 1
                error_metadata = self._extract_error_metadata(e, args, kwargs)

                # Check if it's a PDF fallback
                if self._is_pdf_fallback(e):
                    pdf_fallback_count += 1
                    error_metadata["processing_status"] = "pdf_fallback"
                else:
                    error_metadata["processing_status"] = "error"

                logger.error(
                    f"Error in {self.doc_type} pipeline: {str(e)}",
                    exc_info=True,
                    extra={
                        "doc_type": self.doc_type,
                        "error_type": type(e).__name__,
                        "error_count": error_count,
                        **error_metadata
                    }
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
                        "total_errors": error_count,
                        "pdf_fallbacks": pdf_fallback_count,
                        "elapsed_seconds": elapsed,
                        "docs_per_second": rate,
                        **params_info
                    }
                )

        return wrapper

    def _extract_params_info(self, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """Extract relevant parameters for logging."""
        info = {}

        # Common parameters across pipelines
        if 'years' in kwargs:
            info['years'] = kwargs['years']
        elif len(args) > 1 and isinstance(args[1], list):
            info['years'] = args[1]

        if 'types' in kwargs:
            info['types'] = kwargs['types']
        elif len(args) > 0 and isinstance(args[0], list):
            info['types'] = args[0]

        if 'limit' in kwargs:
            info['limit'] = kwargs['limit']

        return info

    def _extract_doc_metadata(self, doc: T) -> Dict[str, Any]:
        """Extract metadata from a document for logging."""
        metadata = {}

        # Common fields across document types
        if hasattr(doc, 'id'):
            metadata['doc_id'] = doc.id

            # Try to extract year and type from ID
            year_match = re.search(r'/(\d{4})/', str(doc.id))
            if year_match:
                metadata['doc_year'] = int(year_match.group(1))

            type_match = re.search(r'/([a-z]+)/', str(doc.id))
            if type_match:
                metadata['doc_subtype'] = type_match.group(1)

        if hasattr(doc, 'title'):
            metadata['doc_title'] = doc.title[:100]  # Truncate long titles

        return metadata

    def _extract_error_metadata(self, error: Exception, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """Extract metadata from an error for structured logging."""
        metadata = {}

        # Try to extract document information from error message
        error_msg = str(error)

        # Extract URL if present
        url_match = re.search(r'https?://[^\s]+', error_msg)
        if url_match:
            metadata['error_url'] = url_match.group(0)

        # Extract document ID if present
        id_match = re.search(r'/(ukpga|uksi|ukla|[a-z]+)/(\d{4})/(\d+)', error_msg)
        if id_match:
            metadata['doc_id'] = f"{id_match.group(1)}/{id_match.group(2)}/{id_match.group(3)}"
            metadata['doc_type_specific'] = id_match.group(1)
            metadata['doc_year'] = int(id_match.group(2))

        return metadata

    def _is_pdf_fallback(self, error: Exception) -> bool:
        """Check if the error indicates a PDF fallback."""
        error_msg = str(error).lower()
        return "no body found" in error_msg or "likely a pdf" in error_msg
