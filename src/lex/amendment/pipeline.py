import logging
import uuid
from typing import Iterator

from lex.core.pipeline_utils import PipelineMonitor, process_documents

from .models import Amendment
from .parser import AmendmentParser
from .scraper import AmendmentScraper

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="amendment", track_progress=True)
def pipe_amendments(years: list[int], limit: int, **kwargs) -> Iterator[Amendment]:
    scraper = AmendmentScraper()
    parser = AmendmentParser()
    run_id = str(uuid.uuid4())

    logger.info(f"Starting amendment pipeline: run_id={run_id}")

    # Amendment doesn't have types, pass None
    yield from process_documents(
        years=years,
        types=[None],
        loader_or_scraper=scraper,
        parser=parser,
        document_type=Amendment,
        limit=limit,
        wrap_result=False,
        doc_type_name="amendment",
        run_id=run_id,
        clear_tracking=kwargs.get("clear_checkpoint", False),
    )
