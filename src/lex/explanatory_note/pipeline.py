import logging
from typing import Iterator, Optional

from lex.core.document import generate_documents
from lex.explanatory_note.models import ExplanatoryNote
from lex.explanatory_note.scraper import ExplanatoryNoteScraperAndParser
from lex.legislation.models import LegislationType
from lex.settings import YEARS

logger = logging.getLogger(__name__)


def pipe_explanatory_notes(
    types: list[str] = list(LegislationType),
    years: list[str] = YEARS,
    limit: Optional[int] = None,
    **kwargs,
) -> Iterator[ExplanatoryNote]:
    """Generate explanatory notes documents for Elasticsearch.

    Args:
        index: The Elasticsearch index.
        non_interactive: Whether to skip confirmation prompts.
        legislation_types: List of legislation types to include.
        legislation_years: List of legislation years to include.
        limit: Limit number of files to process.

    Returns:
        Iterator of ExplanatoryNote documents.
    """

    scraper_and_parser = ExplanatoryNoteScraperAndParser()

    try:
        explanatory_notes = scraper_and_parser.scrape_and_parse_content(
            years=years, types=types, limit=limit
        )

        # Convert generator to list to count items
        notes_list = list(explanatory_notes)

        if notes_list:
            logger.info(
                f"Processing {len(notes_list)} explanatory notes",
                extra={
                    "doc_type": "explanatory_note",
                    "processing_status": "success",
                    "note_count": len(notes_list),
                },
            )

        yield from generate_documents(notes_list, ExplanatoryNote)

    except Exception as e:
        logger.error(
            f"Error processing explanatory notes: {e}",
            exc_info=True,
            extra={
                "doc_type": "explanatory_note",
                "processing_status": "error",
                "error_type": type(e).__name__,
            },
        )
