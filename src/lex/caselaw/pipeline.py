import logging
import time
from typing import Iterable, List, Set, Dict, Any
from datetime import datetime

from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.caselaw.parser import CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.document import generate_documents
from lex.core.exceptions import LexParsingError
from lex.core.checkpoint import PipelineCheckpoint
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)


def pipe_caselaw(
    years: list[int],
    limit: int,
    types: list[Court] | None = None,
    use_checkpoint: bool = True,
    checkpoint_id: str | None = None,
    clear_checkpoint: bool = False,
    **kwargs,
) -> Iterable[Caselaw]:
    """
    Caselaw pipeline with checkpoint support and improved logging.

    Args:
        years: List of years to process
        limit: Maximum number of cases to process
        types: Optional list of court types to filter
        use_checkpoint: Whether to use checkpoint functionality
        checkpoint_id: Optional checkpoint ID (auto-generated if not provided)
        clear_checkpoint: Whether to clear existing checkpoint
        **kwargs: Additional arguments

    Yields:
        Caselaw documents
    """
    scraper = CaselawScraper()
    parser = CaselawParser()

    # Initialize checkpoint if enabled
    checkpoint = None
    processed_urls: Set[str] = set()
    failed_urls: Dict[str, str] = {}
    completed_combinations: Set[str] = set()

    if use_checkpoint:
        # Generate checkpoint ID if not provided
        if not checkpoint_id:
            parts = ["caselaw"]
            if years:
                parts.extend([str(min(years)), str(max(years))])
            if types:
                parts.extend([t.value for t in sorted(types, key=lambda x: x.value)])
            checkpoint_id = "_".join(parts)

        checkpoint = PipelineCheckpoint(checkpoint_id)

        if clear_checkpoint:
            checkpoint.clear()
            logger.info(f"Cleared checkpoint: {checkpoint_id}")
        else:
            # Load existing state
            state = checkpoint.get_state()
            processed_urls = state.get("processed_urls", set())
            failed_urls = state.get("failed_urls", {})
            completed_combinations = checkpoint.get_completed_combinations()

            logger.info(
                f"Resuming from checkpoint: {checkpoint_id}",
                extra={
                    "checkpoint_id": checkpoint_id,
                    "processed_count": len(processed_urls),
                    "failed_count": len(failed_urls),
                    "completed_combinations": len(completed_combinations),
                },
            )

    # Track statistics
    total_processed = 0
    total_skipped = 0
    total_errors = 0
    start_time = time.time()
    last_progress_time = time.time()

    # Process by court/year combinations for efficient resumption
    court_types = types or list(Court)

    for court in court_types:
        for year in sorted(years):
            combination_key = f"{court.value}_{year}"

            # Skip if this combination is already complete
            if combination_key in completed_combinations:
                logger.debug(
                    f"Skipping completed combination: {combination_key}",
                    extra={"court": court.value, "year": year, "combination_key": combination_key},
                )
                continue

            combination_start_time = time.time()
            combination_processed = 0
            combination_errors = 0

            logger.info(
                f"Processing court/year combination: {combination_key}",
                extra={"court": court.value, "year": year, "combination_key": combination_key},
            )

            try:
                # Process cases for this court/year combination
                for soup, case_url in scraper.load_content(
                    years=[year], limit=limit, types=[court]
                ):
                    # Extract additional metadata from soup
                    case_id = None
                    case_number = None

                    try:
                        # Extract metadata from soup
                        if soup and hasattr(soup, "find"):
                            # Try to get ID from metadata
                            id_elem = soup.find("uk:cite")
                            if id_elem:
                                case_id = id_elem.get_text()
                    except Exception as e:
                        logger.debug(f"Could not extract metadata from soup: {e}")

                    # Skip if already processed
                    if case_url and case_url in processed_urls:
                        total_skipped += 1
                        continue

                    try:
                        # Parse the caselaw
                        caselaw = parser.parse_content(soup)

                        # Update case_url with actual ID if we have it
                        if caselaw.id:
                            case_url = caselaw.id
                            case_id = caselaw.id
                            case_number = caselaw.number

                        # Log successful parsing with rich metadata
                        logger.info(
                            f"Parsed case: {case_id}",
                            extra={
                                "doc_id": case_id,
                                "court": court.value,
                                "doc_year": year,
                                "case_number": case_number,
                                "cite_as": getattr(caselaw, "cite_as", None),
                                "processing_status": "success",
                                "has_xml": True,
                                "case_name": caselaw.name[:100] if caselaw.name else None,
                                "combination_key": combination_key,
                            },
                        )

                        # Yield the document
                        yield from generate_documents([caselaw], Caselaw)

                        # Update checkpoint
                        total_processed += 1
                        combination_processed += 1
                        if checkpoint and case_url:
                            processed_urls.add(case_url)
                            checkpoint.mark_processed(case_url)

                    except LexParsingError as e:
                        total_errors += 1
                        combination_errors += 1
                        error_msg = str(e)

                        # Determine if this is a PDF fallback
                        is_pdf_fallback = (
                            "pdf" in error_msg.lower() or "no body found" in error_msg.lower()
                        )

                        logger.error(
                            f"Error parsing caselaw: {error_msg}",
                            extra={
                                "doc_id": case_id,
                                "court": court.value,
                                "doc_year": year,
                                "processing_status": "pdf_fallback"
                                if is_pdf_fallback
                                else "parse_error",
                                "error_type": "LexParsingError",
                                "has_xml": False,
                                "is_pdf_fallback": is_pdf_fallback,
                                "combination_key": combination_key,
                            },
                        )

                        # Update checkpoint with failure
                        if checkpoint and case_url:
                            failed_urls[case_url] = error_msg
                            checkpoint.mark_failed(case_url, error_msg)

                    except HTTPError as e:
                        if e.response.status_code >= 500:
                            # Server error - log but continue
                            logger.error(
                                f"Server error for case {case_id}: {e}",
                                extra={
                                    "doc_id": case_id,
                                    "court": court.value,
                                    "doc_year": year,
                                    "http_status": e.response.status_code,
                                    "processing_status": "server_error",
                                    "error_type": "HTTPError",
                                    "combination_key": combination_key,
                                },
                            )
                            total_errors += 1
                            combination_errors += 1
                        else:
                            raise

                    except Exception as e:
                        total_errors += 1
                        combination_errors += 1
                        logger.error(
                            f"Error parsing caselaw: {e}",
                            exc_info=True,
                            extra={
                                "doc_id": case_id,
                                "court": court.value,
                                "doc_year": year,
                                "processing_status": "error",
                                "error_type": type(e).__name__,
                                "combination_key": combination_key,
                            },
                        )

                        # Update checkpoint with failure
                        if checkpoint and case_url:
                            failed_urls[case_url] = str(e)
                            checkpoint.mark_failed(case_url, str(e))

                    # Progress logging
                    current_time = time.time()
                    if current_time - last_progress_time >= 10:  # Every 10 seconds
                        elapsed = current_time - start_time
                        rate = total_processed / elapsed if elapsed > 0 else 0

                        logger.info(
                            f"Progress update: {total_processed} cases processed, {total_skipped} skipped, {total_errors} errors",
                            extra={
                                "total_processed": total_processed,
                                "total_skipped": total_skipped,
                                "total_errors": total_errors,
                                "processing_rate": rate,
                                "elapsed_seconds": elapsed,
                                "current_combination": combination_key,
                            },
                        )
                        last_progress_time = current_time

                # Mark combination as complete
                if checkpoint:
                    checkpoint.mark_combination_complete(combination_key)
                    completed_combinations.add(combination_key)

                # Log combination summary
                combination_elapsed = time.time() - combination_start_time
                logger.info(
                    f"Completed combination {combination_key}: {combination_processed} processed, {combination_errors} errors",
                    extra={
                        "combination_key": combination_key,
                        "court": court.value,
                        "year": year,
                        "processed": combination_processed,
                        "errors": combination_errors,
                        "duration_seconds": combination_elapsed,
                    },
                )

            except Exception as e:
                logger.error(
                    f"Fatal error processing combination {combination_key}: {e}",
                    exc_info=True,
                    extra={
                        "combination_key": combination_key,
                        "court": court.value,
                        "year": year,
                        "error_type": type(e).__name__,
                    },
                )
                # Continue with next combination
                continue

    # Final summary
    total_elapsed = time.time() - start_time
    logger.info(
        f"Caselaw pipeline complete: {total_processed} processed, {total_skipped} skipped, {total_errors} errors",
        extra={
            "total_processed": total_processed,
            "total_skipped": total_skipped,
            "total_errors": total_errors,
            "duration_seconds": total_elapsed,
            "duration_minutes": total_elapsed / 60,
            "avg_docs_per_second": total_processed / total_elapsed if total_elapsed > 0 else 0,
            "checkpoint_id": checkpoint_id if checkpoint else None,
        },
    )


def pipe_caselaw_sections(
    years: list[int],
    limit: int,
    types: list[Court] | None = None,
    use_checkpoint: bool = True,
    checkpoint_id: str | None = None,
    clear_checkpoint: bool = False,
    **kwargs,
) -> Iterable[CaselawSection]:
    """
    Caselaw sections pipeline with checkpoint support and improved logging.

    Similar to pipe_caselaw but for case sections.
    """
    scraper = CaselawScraper()
    parser = CaselawSectionParser()

    # Initialize checkpoint if enabled
    checkpoint = None
    processed_urls: Set[str] = set()
    failed_urls: Dict[str, str] = {}
    completed_combinations: Set[str] = set()

    if use_checkpoint:
        # Generate checkpoint ID if not provided
        if not checkpoint_id:
            parts = ["caselaw_sections"]
            if years:
                parts.extend([str(min(years)), str(max(years))])
            if types:
                parts.extend([t.value for t in sorted(types, key=lambda x: x.value)])
            checkpoint_id = "_".join(parts)

        checkpoint = PipelineCheckpoint(checkpoint_id)

        if clear_checkpoint:
            checkpoint.clear()
            logger.info(f"Cleared checkpoint: {checkpoint_id}")
        else:
            # Load existing state
            state = checkpoint.get_state()
            processed_urls = state.get("processed_urls", set())
            failed_urls = state.get("failed_urls", {})
            completed_combinations = checkpoint.get_completed_combinations()

            logger.info(
                f"Resuming from checkpoint: {checkpoint_id}",
                extra={
                    "checkpoint_id": checkpoint_id,
                    "processed_count": len(processed_urls),
                    "failed_count": len(failed_urls),
                    "completed_combinations": len(completed_combinations),
                },
            )

    # Track statistics
    total_processed = 0
    total_skipped = 0
    total_errors = 0
    total_sections = 0
    start_time = time.time()
    last_progress_time = time.time()

    # Process by court/year combinations
    court_types = types or list(Court)

    for court in court_types:
        for year in sorted(years):
            combination_key = f"{court.value}_{year}"

            # Skip if this combination is already complete
            if combination_key in completed_combinations:
                logger.debug(
                    f"Skipping completed combination: {combination_key}",
                    extra={"court": court.value, "year": year, "combination_key": combination_key},
                )
                continue

            combination_start_time = time.time()
            combination_processed = 0
            combination_sections = 0
            combination_errors = 0

            logger.info(
                f"Processing court/year combination: {combination_key}",
                extra={"court": court.value, "year": year, "combination_key": combination_key},
            )

            try:
                # Process cases for this court/year combination
                for soup, case_url in scraper.load_content(
                    years=[year], limit=limit, types=[court]
                ):
                    # Extract additional metadata from soup
                    case_id = None

                    try:
                        # Extract metadata from soup
                        if soup and hasattr(soup, "find"):
                            # Try to get ID from metadata
                            id_elem = soup.find("uk:cite")
                            if id_elem:
                                case_id = id_elem.get_text()
                    except Exception as e:
                        logger.debug(f"Could not extract metadata from soup: {e}")

                    # Skip if already processed
                    if case_url and case_url in processed_urls:
                        total_skipped += 1
                        continue

                    try:
                        # Parse the caselaw sections
                        caselaw_sections = parser.parse_content(soup)

                        # Update case_url with actual ID if we have it
                        if caselaw_sections and len(caselaw_sections) > 0:
                            # Get case ID from first section
                            first_section = caselaw_sections[0]
                            if hasattr(first_section, "caselaw_id"):
                                case_id = first_section.caselaw_id
                                case_url = case_id

                        section_count = len(caselaw_sections)

                        # Log successful parsing with rich metadata
                        logger.info(
                            f"Parsed case sections: {case_id}",
                            extra={
                                "doc_id": case_id,
                                "court": court.value,
                                "doc_year": year,
                                "section_count": section_count,
                                "processing_status": "success",
                                "has_xml": True,
                                "combination_key": combination_key,
                            },
                        )

                        # Yield the sections
                        yield from generate_documents(caselaw_sections, CaselawSection)

                        # Update checkpoint
                        total_processed += 1
                        total_sections += section_count
                        combination_processed += 1
                        combination_sections += section_count

                        if checkpoint and case_url:
                            processed_urls.add(case_url)
                            checkpoint.mark_processed(case_url)

                    except LexParsingError as e:
                        total_errors += 1
                        combination_errors += 1
                        error_msg = str(e)

                        # Determine if this is a PDF fallback
                        is_pdf_fallback = (
                            "pdf" in error_msg.lower() or "no body found" in error_msg.lower()
                        )

                        logger.error(
                            f"Error parsing caselaw sections: {error_msg}",
                            extra={
                                "doc_id": case_id,
                                "court": court.value,
                                "doc_year": year,
                                "processing_status": "pdf_fallback"
                                if is_pdf_fallback
                                else "parse_error",
                                "error_type": "LexParsingError",
                                "has_xml": False,
                                "is_pdf_fallback": is_pdf_fallback,
                                "combination_key": combination_key,
                            },
                        )

                        # Update checkpoint with failure
                        if checkpoint and case_url:
                            failed_urls[case_url] = error_msg
                            checkpoint.mark_failed(case_url, error_msg)

                    except Exception as e:
                        total_errors += 1
                        combination_errors += 1
                        logger.error(
                            f"Error parsing caselaw sections: {e}",
                            exc_info=True,
                            extra={
                                "doc_id": case_id,
                                "court": court.value,
                                "doc_year": year,
                                "processing_status": "error",
                                "error_type": type(e).__name__,
                                "combination_key": combination_key,
                            },
                        )

                        # Update checkpoint with failure
                        if checkpoint and case_url:
                            failed_urls[case_url] = str(e)
                            checkpoint.mark_failed(case_url, str(e))

                    # Progress logging
                    current_time = time.time()
                    if current_time - last_progress_time >= 10:  # Every 10 seconds
                        elapsed = current_time - start_time
                        rate = total_processed / elapsed if elapsed > 0 else 0

                        logger.info(
                            f"Progress update: {total_processed} cases processed ({total_sections} sections), "
                            f"{total_skipped} skipped, {total_errors} errors",
                            extra={
                                "total_processed": total_processed,
                                "total_sections": total_sections,
                                "total_skipped": total_skipped,
                                "total_errors": total_errors,
                                "processing_rate": rate,
                                "elapsed_seconds": elapsed,
                                "current_combination": combination_key,
                            },
                        )
                        last_progress_time = current_time

                # Mark combination as complete
                if checkpoint:
                    checkpoint.mark_combination_complete(combination_key)
                    completed_combinations.add(combination_key)

                # Log combination summary
                combination_elapsed = time.time() - combination_start_time
                logger.info(
                    f"Completed combination {combination_key}: {combination_processed} processed "
                    f"({combination_sections} sections), {combination_errors} errors",
                    extra={
                        "combination_key": combination_key,
                        "court": court.value,
                        "year": year,
                        "processed": combination_processed,
                        "sections": combination_sections,
                        "errors": combination_errors,
                        "duration_seconds": combination_elapsed,
                    },
                )

            except Exception as e:
                logger.error(
                    f"Fatal error processing combination {combination_key}: {e}",
                    exc_info=True,
                    extra={
                        "combination_key": combination_key,
                        "court": court.value,
                        "year": year,
                        "error_type": type(e).__name__,
                    },
                )
                # Continue with next combination
                continue

    # Final summary
    total_elapsed = time.time() - start_time
    logger.info(
        f"Caselaw sections pipeline complete: {total_processed} cases processed ({total_sections} sections), "
        f"{total_skipped} skipped, {total_errors} errors",
        extra={
            "total_processed": total_processed,
            "total_sections": total_sections,
            "total_skipped": total_skipped,
            "total_errors": total_errors,
            "duration_seconds": total_elapsed,
            "duration_minutes": total_elapsed / 60,
            "avg_docs_per_second": total_processed / total_elapsed if total_elapsed > 0 else 0,
            "checkpoint_id": checkpoint_id if checkpoint else None,
        },
    )
