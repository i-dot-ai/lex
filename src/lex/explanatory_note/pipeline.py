import logging
from typing import Iterator, Optional

from lex.core.document import generate_documents
from lex.core.error_utils import ErrorCategorizer
from lex.core.pipeline_utils import PipelineMonitor, checkpoint_manager
from lex.explanatory_note.models import ExplanatoryNote
from lex.explanatory_note.scraper import ExplanatoryNoteScraperAndParser
from lex.legislation.models import LegislationType
from lex.settings import YEARS

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="explanatory_note", track_progress=True)
def pipe_explanatory_note(
    types: list[str] = list(LegislationType),
    years: list[str] = YEARS,
    limit: Optional[int] = None,
    use_checkpoint: bool = False,
    clear_checkpoint: bool = False,
    **kwargs,
) -> Iterator[ExplanatoryNote]:
    """Generate explanatory notes documents for Elasticsearch with checkpoint support.

    Args:
        types: List of legislation types to include.
        years: List of legislation years to include.
        limit: Limit number of files to process.
        use_checkpoint: Whether to use checkpointing.
        clear_checkpoint: Whether to clear existing checkpoint.

    Returns:
        Iterator of ExplanatoryNote documents.
    """

    scraper_and_parser = ExplanatoryNoteScraperAndParser()

    # Generate checkpoint ID
    checkpoint_id = "explanatory_note"
    if years:
        checkpoint_id += f"_{min(years)}_{max(years)}"
    if types and len(types) < len(list(LegislationType)):
        # Add types to ID only if not all types
        checkpoint_id += "_" + "_".join(sorted(types[:3]))  # First 3 types

    with checkpoint_manager("explanatory_note", use_checkpoint, clear_checkpoint, checkpoint_id) as checkpoint:
        # Process by type/year combinations for better checkpoint granularity
        for type_name, year in checkpoint.should_process_combination(types, years):
            combination_key = f"{type_name}_{year}"

            try:
                # Process notes for this type/year combination
                for url, note in scraper_and_parser.scrape_and_parse_content(
                    years=[year], types=[type_name], limit=limit
                ):
                    # Use legislation_id as unique key
                    if hasattr(note, 'legislation_id') and note.legislation_id:
                        url_key = note.legislation_id
                    else:
                        url_key = f"{type_name}_{year}_{note.id}"

                    if checkpoint.is_processed(url_key):
                        continue

                    try:
                        yield from generate_documents([note], ExplanatoryNote)
                        checkpoint.mark_processed(url_key, {
                            "type": type_name,
                            "year": year,
                            "note_type": note.note_type if hasattr(note, 'note_type') else None
                        })
                    except Exception as e:
                        if ErrorCategorizer.is_recoverable_error(e):
                            logger.error(
                                ErrorCategorizer.get_error_summary(e),
                                extra=ErrorCategorizer.extract_error_metadata(e)
                            )
                            checkpoint.mark_failed(url_key, e)
                        else:
                            raise

                # Mark combination complete
                checkpoint.mark_combination_completed(combination_key)

            except Exception as e:
                logger.error(f"Failed to process combination {combination_key}: {e}", exc_info=True)
                continue
