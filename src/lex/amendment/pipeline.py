import logging
from typing import Iterator

from lex.core.checkpoint import get_checkpoints
from lex.core.pipeline_utils import PipelineMonitor, process_checkpoints

from .models import Amendment
from .parser import AmendmentParser
from .scraper import AmendmentScraper

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="amendment", track_progress=True)
def pipe_amendments(years: list[int], limit: int, **kwargs) -> Iterator[Amendment]:
    scraper = AmendmentScraper()
    parser = AmendmentParser()

    checkpoints = get_checkpoints(years, None, "amendment", kwargs.get("clear_checkpoint", False))

    yield from process_checkpoints(
        checkpoints=checkpoints,
        loader_or_scraper=scraper,
        parser=parser,
        document_type=Amendment,
        limit=limit,
        wrap_result=False,
    )
