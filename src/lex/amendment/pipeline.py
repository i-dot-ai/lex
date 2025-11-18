import logging
import uuid
from typing import Iterator

from lex.core.pipeline_utils import PipelineMonitor, process_documents
from lex.processing.amendment_explanations.explanation_generator import (
    add_explanations_to_amendments,
)

from .models import Amendment
from .parser import AmendmentParser
from .scraper import AmendmentScraper

logger = logging.getLogger(__name__)


@PipelineMonitor(doc_type="amendment", track_progress=True)
def pipe_amendments(years: list[int], limit: int, **kwargs) -> Iterator[Amendment]:
    scraper = AmendmentScraper()
    parser = AmendmentParser()
    run_id = str(uuid.uuid4())

    generate_explanations = kwargs.get("generate_explanations", False)
    explanation_batch_size = kwargs.get("explanation_batch_size", 10)

    logger.info(
        f"Starting amendment pipeline: run_id={run_id}, generate_explanations={generate_explanations}"
    )

    # Process documents in batches if generating explanations
    if generate_explanations:
        batch = []
        for amendment in process_documents(
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
        ):
            batch.append(amendment)

            # Process batch when full
            if len(batch) >= explanation_batch_size:
                logger.info(f"Generating explanations for batch of {len(batch)} amendments")
                batch_with_explanations = add_explanations_to_amendments(batch)
                for amendment in batch_with_explanations:
                    yield amendment
                batch = []

        # Process remaining amendments in final batch
        if batch:
            logger.info(f"Generating explanations for final batch of {len(batch)} amendments")
            batch_with_explanations = add_explanations_to_amendments(batch)
            for amendment in batch_with_explanations:
                yield amendment
    else:
        # No explanation generation - pass through
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
