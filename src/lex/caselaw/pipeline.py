import logging
from typing import Iterator, Tuple, Union

from lex.caselaw.models import Caselaw, CaselawSection, Court
from lex.caselaw.parser import CaselawAndCaselawSectionsParser, CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.checkpoint import get_checkpoints
from lex.core.pipeline_utils import PipelineMonitor, process_checkpoints

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="caselaw", track_progress=True)
def pipe_caselaw(years: list[int], limit: int, types: list[Court], **kwargs) -> Iterator[Caselaw]:
    scraper = CaselawScraper()
    parser = CaselawParser()

    checkpoints = get_checkpoints(years, types, "caselaw", kwargs.get("clear_checkpoint", False))

    yield from process_checkpoints(
        checkpoints=checkpoints,
        loader_or_scraper=scraper,
        parser=parser,
        document_type=Caselaw,
        limit=limit,
        wrap_result=True,
    )


@PipelineMonitor(doc_type="caselaw_section", track_progress=True)
def pipe_caselaw_sections(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[CaselawSection]:
    scraper = CaselawScraper()
    parser = CaselawSectionParser()

    checkpoints = get_checkpoints(
        years, types, "caselaw_section", kwargs.get("clear_checkpoint", False)
    )

    yield from process_checkpoints(
        checkpoints=checkpoints,
        loader_or_scraper=scraper,
        parser=parser,
        document_type=CaselawSection,
        limit=limit,
        wrap_result=False,
    )


def pipe_caselaw_unified(
    years: list[int], limit: int, types: list[Court], **kwargs
) -> Iterator[Tuple[str, Union[Caselaw, CaselawSection]]]:
    """
    Unified pipeline that yields both Caselaw and CaselawSection documents.
    Downloads each case XML once and extracts both document types.
    
    Yields:
        Tuples of (index_type, document) where index_type is 'caselaw' or 'caselaw-section'
    """
    scraper = CaselawScraper()
    parser = CaselawAndCaselawSectionsParser()
    
    checkpoints = get_checkpoints(years, types, "caselaw_unified", kwargs.get("clear_checkpoint", False))
    
    remaining_limit = limit if limit is not None else float("inf")
    
    for checkpoint in checkpoints:
        with checkpoint as ctx:
            if ctx.is_complete():
                continue
                
            # Pass None for limit if we want all documents
            passed_limit = None if limit is None else int(remaining_limit)
            content_iterator = scraper.load_content(
                years=[checkpoint.year], 
                types=[checkpoint.doc_type], 
                limit=passed_limit
            )
            
            for url, soup in content_iterator:
                if remaining_limit <= 0:
                    logger.info("Document limit reached during processing")
                    ctx.mark_limit_hit()
                    return
                
                # Parse once, get both document types
                result = ctx.process_item(url, lambda: parser.parse_content(soup))
                if result:
                    caselaw, sections = result
                    remaining_limit -= 1
                    
                    # Yield the main caselaw document
                    yield ("caselaw", caselaw)
                    
                    # Yield all section documents
                    for section in sections:
                        yield ("caselaw-section", section)
