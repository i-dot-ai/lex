"""Pipeline utilities for cross-cutting concerns like monitoring and logging."""

import logging
import re
import time
from functools import wraps
from typing import Any, Callable, Dict, Iterator, Type, TypeVar

from lex.core.document import generate_documents
from lex.core.models import LexModel

T = TypeVar("T", bound=LexModel)


class PipelineMonitor:
    """Decorator for pipeline monitoring and structured logging."""

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

            params_info = self._extract_params_info(args, kwargs)

            logger.info(
                f"Starting {self.doc_type} pipeline",
                extra={"doc_type": self.doc_type, "pipeline_status": "started", **params_info},
            )

            try:
                for doc in func(*args, **kwargs):
                    doc_count += 1

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

        if hasattr(doc, "id"):
            metadata["doc_id"] = doc.id

            year_match = re.search(r"/(\d{4})/", str(doc.id))
            if year_match:
                metadata["doc_year"] = int(year_match.group(1))

            type_match = re.search(r"/([a-z]+)/", str(doc.id))
            if type_match:
                metadata["doc_subtype"] = type_match.group(1)

        if hasattr(doc, "title"):
            metadata["doc_title"] = doc.title[:100]

        return metadata


def process_documents(
    years: list[int],
    types: list[Any],
    loader_or_scraper: Any,
    parser: Any,
    document_type: Type[LexModel],
    limit: int,
    wrap_result: bool = False,
    doc_type_name: str = None,
    run_id: str = None,
    clear_tracking: bool = False,
) -> Iterator[LexModel]:
    """Process documents with URL tracking, relying on Qdrant UUID5 idempotency.

    Args:
        years: List of years to process
        types: List of document types to process
        loader_or_scraper: Content loader or scraper instance
        parser: Parser instance with parse_content method
        document_type: The document model class to generate
        limit: Processing limit (None = no limit)
        wrap_result: Whether to wrap the parser result in a list
        doc_type_name: Document type name for tracking (e.g., 'legislation', 'caselaw')
        run_id: Run ID for this pipeline execution
        clear_tracking: Whether to clear existing tracking files

    Yields:
        Processed documents of the specified type
    """
    import uuid
    from lex.core.url_tracker import URLTracker, clear_tracking as clear_tracking_fn
    from lex.core.document import uri_to_uuid
    from lex.core.exceptions import ProcessedException

    logger = logging.getLogger(__name__)

    if clear_tracking and doc_type_name:
        clear_tracking_fn(doc_type_name)

    run_id = run_id or str(uuid.uuid4())
    remaining_limit = limit if limit is not None else float("inf")

    for year in years:
        if remaining_limit <= 0:
            logger.info(f"Document limit reached at year {year}")
            break

        for doc_type in types:
            if remaining_limit <= 0:
                logger.info(f"Document limit reached at type {doc_type.value}, year {year}")
                break

            type_value = doc_type.value if hasattr(doc_type, 'value') else str(doc_type)
            tracker = URLTracker(doc_type_name, year, type_value, run_id) if doc_type_name else None

            if tracker:
                stats = tracker.get_stats()
                logger.info(f"Processing {type_value} for year {year}: {stats['success']} done, {stats['failures']} failed")
            else:
                logger.info(f"Processing {type_value} for year {year}")

            passed_limit = None if limit is None else int(remaining_limit)
            content_iterator = loader_or_scraper.load_content(
                years=[year], types=[doc_type], limit=passed_limit
            )

            for url, soup in content_iterator:
                if remaining_limit <= 0:
                    logger.info("Document limit reached during processing")
                    return

                if tracker and tracker.is_processed(url):
                    logger.debug(f"Skipping already processed: {url}")
                    continue

                try:
                    result = parser.parse_content(soup)
                    if result:
                        data_to_process = [result] if wrap_result else result

                        for doc in generate_documents(data_to_process, document_type):
                            if tracker:
                                doc_uuid = uri_to_uuid(doc.id)
                                doc_date = None
                                if hasattr(doc, 'date') and doc.date:
                                    doc_date = str(doc.date)
                                tracker.record_success(url, doc_uuid, doc_date)

                            remaining_limit -= 1
                            yield doc

                except ProcessedException as e:
                    if tracker:
                        tracker.record_failure(url, f"ProcessedException: {str(e)}")
                    logger.info(f"Skipping {url}: {str(e)}")
                    continue

                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    if tracker:
                        tracker.record_failure(url, error_msg)
                    logger.warning(f"Failed to parse {url}: {e}", exc_info=False)
                    continue
