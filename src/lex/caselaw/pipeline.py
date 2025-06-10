import logging
from typing import Iterable

from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.caselaw.parser import CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.document import generate_documents
from lex.core.error_utils import ErrorCategorizer
from lex.core.pipeline_utils import PipelineMonitor, checkpoint_manager

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="caselaw", track_progress=True)
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

    # Generate checkpoint ID if needed
    if use_checkpoint and not checkpoint_id:
        parts = ["caselaw"]
        if years:
            parts.extend([str(min(years)), str(max(years))])
        if types:
            parts.extend([t.value for t in sorted(types, key=lambda x: x.value)])
        checkpoint_id = "_".join(parts)

    # Use checkpoint manager for all checkpoint operations
    with checkpoint_manager("caselaw", use_checkpoint, clear_checkpoint, checkpoint_id) as checkpoint:
        court_types = types or list(Court)

        # Process combinations with checkpoint support
        for court, year in checkpoint.should_process_combination(
            [c.value for c in court_types], years
        ):
            # Convert string back to Court enum
            court_enum = next(c for c in Court if c.value == court)
            combination_key = f"{court}_{year}"

            try:
                # Process cases for this combination
                for case_url, soup in scraper.load_content(
                    years=[year], limit=limit, types=[court_enum]
                ):
                    # Skip if already processed
                    if checkpoint.is_processed(case_url):
                        continue

                    try:
                        # Parse the caselaw - simple business logic
                        caselaw = parser.parse_content(soup)

                        # Update URL with actual ID if available
                        if caselaw.id:
                            case_url = caselaw.id

                        # Yield documents and mark as processed
                        yield from generate_documents([caselaw], Caselaw)
                        checkpoint.mark_processed(case_url, {
                            "court": court,
                            "year": year,
                            "case_number": caselaw.number,
                            "case_name": caselaw.name[:100] if caselaw.name else None
                        })

                    except Exception as e:
                        # Use error categorizer for consistent handling
                        metadata = ErrorCategorizer.extract_error_metadata(e, {
                            "court": court,
                            "year": year,
                            "combination_key": combination_key
                        })

                        if ErrorCategorizer.is_recoverable_error(e):
                            # Log and continue
                            logger.error(
                                ErrorCategorizer.get_error_summary(e),
                                extra=metadata
                            )
                            checkpoint.mark_failed(case_url, e, metadata)
                        else:
                            # Non-recoverable error
                            raise


                # Mark combination as complete
                checkpoint.mark_combination_completed(combination_key)

            except Exception as e:
                # Log combination-level errors and continue
                logger.error(
                    f"Failed to process combination {combination_key}: {e}",
                    exc_info=True,
                    extra={
                        "combination_key": combination_key,
                        "court": court,
                        "year": year
                    }
                )
                continue


@PipelineMonitor(doc_type="caselaw_section", track_progress=True)
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

    # Generate checkpoint ID if needed
    if use_checkpoint and not checkpoint_id:
        parts = ["caselaw_sections"]
        if years:
            parts.extend([str(min(years)), str(max(years))])
        if types:
            parts.extend([t.value for t in sorted(types, key=lambda x: x.value)])
        checkpoint_id = "_".join(parts)

    with checkpoint_manager("caselaw_section", use_checkpoint, clear_checkpoint, checkpoint_id) as checkpoint:
        court_types = types or list(Court)

        for court, year in checkpoint.should_process_combination(
            [c.value for c in court_types], years
        ):
            court_enum = next(c for c in Court if c.value == court)
            combination_key = f"{court}_{year}"

            try:
                for soup, case_url in scraper.load_content(
                    years=[year], limit=limit, types=[court_enum]
                ):
                    if checkpoint.is_processed(case_url):
                        continue

                    try:
                        # Parse sections
                        sections = parser.parse_content(soup)

                        if sections:
                            # Update URL with first section's case ID
                            if sections[0].caselaw_id:
                                case_url = sections[0].caselaw_id

                            # Yield all sections
                            yield from generate_documents(sections, CaselawSection)
                            checkpoint.mark_processed(case_url, {
                                "court": court,
                                "year": year,
                                "section_count": len(sections)
                            })

                    except Exception as e:
                        if ErrorCategorizer.is_recoverable_error(e):
                            metadata = ErrorCategorizer.extract_error_metadata(e)
                            logger.error(
                                ErrorCategorizer.get_error_summary(e),
                                extra=metadata
                            )
                            checkpoint.mark_failed(case_url, e, metadata)
                        else:
                            raise


                checkpoint.mark_combination_completed(combination_key)

            except Exception as e:
                logger.error(
                    f"Failed to process combination {combination_key}: {e}",
                    exc_info=True
                )
                continue
