import logging
from typing import Iterator

from lex.core.document import generate_documents
from lex.core.pipeline_utils import PipelineMonitor, checkpoint_manager
from lex.core.error_utils import ErrorCategorizer

from .models import Amendment
from .parser import AmendmentParser
from .scraper import AmendmentScraper

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="amendment", track_progress=True)
def pipe_amendments(
    years: list[int], 
    limit: int,
    use_checkpoint: bool = False,
    clear_checkpoint: bool = False,
    **kwargs
) -> Iterator[Amendment]:
    """Generate amendments documents for Elasticsearch with optional checkpoint support."""
    scraper = AmendmentScraper()
    parser = AmendmentParser()
    
    # Generate checkpoint ID
    checkpoint_id = "amendments"
    if years:
        checkpoint_id += f"_{min(years)}_{max(years)}"
    
    with checkpoint_manager("amendment", use_checkpoint, clear_checkpoint, checkpoint_id) as checkpoint:
        # Since amendments don't have clear year-based combinations like legislation,
        # we'll track individual URLs
        for soup in scraper.load_content(years, limit):
            # Try to extract URL from soup or generate a unique key
            url_key = str(hash(str(soup)[:1000]))  # Use hash of first 1000 chars as key
            
            if checkpoint.is_processed(url_key):
                continue
                
            try:
                amendments = parser.parse_content(soup)
                if amendments:
                    yield from generate_documents(amendments, Amendment)
                    checkpoint.mark_processed(url_key, {
                        "amendment_count": len(amendments)
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
