"""URL-based document processor for generating multiple document types from legislation URLs."""

import logging
from typing import List

from lex.core.document import upload_documents
from lex.explanatory_note.parser import ExplanatoryNoteParser
from lex.legislation.parser.parser import LegislationParser, LegislationSectionParser
from lex.legislation.scraper import LegislationScraper
from lex.settings import EXPLANATORY_NOTE_INDEX, LEGISLATION_INDEX, LEGISLATION_SECTION_INDEX

logger = logging.getLogger(__name__)


def process_urls_to_elasticsearch(
    urls: List[str],
    legislation_index: str = LEGISLATION_INDEX,
    legislation_section_index: str = LEGISLATION_SECTION_INDEX,
    explanatory_note_index: str = EXPLANATORY_NOTE_INDEX,
    batch_size: int = 50,
) -> dict:
    """Process a list of URLs and upload all generated documents to Elasticsearch.

    Args:
        urls: List of legislation URLs to process
        legislation_index: Elasticsearch index for legislation documents
        legislation_section_index: Elasticsearch index for legislation sections
        explanatory_note_index: Elasticsearch index for explanatory notes
        batch_size: Number of documents to process in each batch

    Returns:
        Dictionary with total counts of uploaded documents by type
    """
    scraper = LegislationScraper()
    legislation_parser = LegislationParser()
    legislation_section_parser = LegislationSectionParser()
    explanatory_note_parser = ExplanatoryNoteParser()

    legislation_docs = []
    legislation_section_docs = []
    explanatory_note_docs = []

    total_counts = {
        "legislation": 0,
        "legislation_sections": 0,
        "explanatory_notes": 0
    }

    for i, url in enumerate(urls, 1):
        logger.info(f"Processing URL {i}/{len(urls)}: {url}")

        try:
            # Load content from URL
            soup = scraper.load_legislation_from_url(url)

            # Parse legislation document
            legislation = legislation_parser.parse_content(soup)
            legislation_docs.append(legislation)

            # Parse legislation sections
            sections = legislation_section_parser.parse_content(soup)
            legislation_section_docs.extend(sections)

            # Parse explanatory notes
            explanatory_notes = list(explanatory_note_parser.parse_content(soup))
            explanatory_note_docs.extend(explanatory_notes)

            logger.info(
                f"Processed {url}: {1} legislation, {len(sections)} sections, {len(explanatory_notes)} notes"
            )

        except Exception as e:
            logger.error(f"Error processing {url}: {e}", exc_info=True)
            continue

        # Upload when we have a batch worth of docs OR this is the final iteration
        if len(legislation_docs) >= batch_size or i == len(urls):
            # Upload legislation documents
            if legislation_docs:
                upload_documents(legislation_index, legislation_docs, batch_size=batch_size)
                total_counts["legislation"] += len(legislation_docs)
                logger.info(f"Uploaded {len(legislation_docs)} legislation documents")
                legislation_docs.clear()

            # Upload legislation section documents
            if legislation_section_docs:
                upload_documents(legislation_section_index, legislation_section_docs, batch_size=batch_size)
                total_counts["legislation_sections"] += len(legislation_section_docs)
                logger.info(f"Uploaded {len(legislation_section_docs)} legislation section documents")
                legislation_section_docs.clear()

            # Upload explanatory note documents
            if explanatory_note_docs:
                upload_documents(explanatory_note_index, explanatory_note_docs, batch_size=batch_size)
                total_counts["explanatory_notes"] += len(explanatory_note_docs)
                logger.info(f"Uploaded {len(explanatory_note_docs)} explanatory note documents")
                explanatory_note_docs.clear()

    logger.info(
        f"Completed processing {len(urls)} URLs. "
        f"Total uploaded: {total_counts['legislation']} legislation, "
        f"{total_counts['legislation_sections']} sections, "
        f"{total_counts['explanatory_notes']} notes"
    )

    return total_counts
