import logging
from typing import Iterator

from lex.core.checkpoint import get_checkpoints
from lex.core.document import generate_documents
from lex.core.error_utils import ErrorCategorizer
from lex.core.pipeline_utils import PipelineMonitor

from .models import Amendment
from .parser import AmendmentParser
from .scraper import AmendmentScraper

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="amendment", track_progress=True)
def pipe_amendments(
    years: list[int], limit: int, **kwargs
) -> Iterator[Amendment]:
    scraper = AmendmentScraper()
    parser = AmendmentParser()

    checkpoints = get_checkpoints(years, None, "amendment")

    for checkpoint in checkpoints:
        with checkpoint as ctx:
            for url, soup in scraper.load_content([checkpoint.year], limit):
                result = ctx.process_item(url, lambda: parser.parse_content(soup))
                if result:
                    yield from generate_documents(result, Amendment)
