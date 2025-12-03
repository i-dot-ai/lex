#!/usr/bin/env python
import argparse
import logging
import os
from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Tuple

from dotenv import load_dotenv

load_dotenv()

from lex.amendment.pipeline import pipe_amendments
from lex.amendment.qdrant_schema import get_amendment_schema
from lex.caselaw.models import Court
from lex.caselaw.pipeline import pipe_caselaw, pipe_caselaw_sections, pipe_caselaw_unified
from lex.caselaw.qdrant_schema import get_caselaw_schema, get_caselaw_section_schema
from lex.core import create_collection_if_none, upload_documents
from lex.core.utils import parse_years, set_logging_level
from lex.explanatory_note.pipeline import pipe_explanatory_note
from lex.explanatory_note.qdrant_schema import get_explanatory_note_schema
from lex.legislation.models import LegislationType
from lex.legislation.pipeline import pipe_legislation, pipe_legislation_sections, pipe_legislation_unified
from lex.legislation.qdrant_schema import get_legislation_schema, get_legislation_section_schema
from lex.settings import (
    AMENDMENT_COLLECTION,
    CASELAW_COLLECTION,
    CASELAW_SECTION_COLLECTION,
    EXPLANATORY_NOTE_COLLECTION,
    LEGISLATION_COLLECTION,
    LEGISLATION_SECTION_COLLECTION,
    YEARS,
)

# Environment settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "localhost")

# Set up logging
set_logging_level(
    logging.INFO,
    service_name="pipeline",
    environment=ENVIRONMENT,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Mapping of model to collection name, document iterator, and schema
CollectionMapping = namedtuple("CollectionMapping", ["collection", "pipe", "schema"])

collection_mapping = {
    "legislation": CollectionMapping(
        LEGISLATION_COLLECTION,
        pipe_legislation,
        get_legislation_schema,
    ),
    "legislation-section": CollectionMapping(
        LEGISLATION_SECTION_COLLECTION,
        pipe_legislation_sections,
        get_legislation_section_schema,
    ),
    "caselaw": CollectionMapping(
        CASELAW_COLLECTION,
        pipe_caselaw,
        get_caselaw_schema,
    ),
    "caselaw-section": CollectionMapping(
        CASELAW_SECTION_COLLECTION,
        pipe_caselaw_sections,
        get_caselaw_section_schema,
    ),
    "caselaw-unified": CollectionMapping(
        None,  # Special case - uses multiple collections
        pipe_caselaw_unified,
        None,  # Schemas handled per collection type
    ),
    "legislation-unified": CollectionMapping(
        None,  # Special case - uses multiple collections
        pipe_legislation_unified,
        None,  # Schemas handled per collection type
    ),
    "explanatory-note": CollectionMapping(
        EXPLANATORY_NOTE_COLLECTION,
        pipe_explanatory_note,
        get_explanatory_note_schema,
    ),
    "amendment": CollectionMapping(
        AMENDMENT_COLLECTION,
        pipe_amendments,
        get_amendment_schema,
    ),
}


def process_single_checkpoint(
    year: int, court_type: str, limit: int = None, batch_size: int = 50
) -> Tuple[int, int]:
    """
    Process a single year/court combination for caselaw unified pipeline.
    This function is designed to be run in parallel workers.

    Returns:
        Tuple of (caselaw_count, section_count)
    """
    # Import here to avoid serialization issues with multiprocessing
    from lex.caselaw.models import Court
    from lex.caselaw.pipeline import pipe_caselaw_unified
    from lex.core import upload_documents

    # Set up logging for this process
    process_logger = logging.getLogger(f"worker_{year}_{court_type}")
    process_logger.info(f"Starting processing for {court_type} {year}")

    # Convert string back to Court enum
    court = Court(court_type)

    # Create args-like object for the pipeline
    class Args:
        def __init__(self):
            self.years = [year]
            self.types = [court]
            self.limit = limit
            self.clear_checkpoint = False
            self.batch_size = batch_size

    args = Args()
    documents = pipe_caselaw_unified(**vars(args))

    # Process documents
    caselaw_batch = []
    section_batch = []
    caselaw_count = 0
    section_count = 0

    for index_type, doc in documents:
        if index_type == "caselaw":
            caselaw_batch.append(doc)
            caselaw_count += 1
            if len(caselaw_batch) >= batch_size:
                upload_documents(collection_name=CASELAW_COLLECTION, documents=caselaw_batch)
                caselaw_batch = []

        elif index_type == "caselaw-section":
            section_batch.append(doc)
            section_count += 1
            if len(section_batch) >= batch_size:
                upload_documents(
                    collection_name=CASELAW_SECTION_COLLECTION, documents=section_batch
                )
                section_batch = []

    # Upload remaining batches
    if caselaw_batch:
        upload_documents(collection_name=CASELAW_COLLECTION, documents=caselaw_batch)
    if section_batch:
        upload_documents(collection_name=CASELAW_SECTION_COLLECTION, documents=section_batch)

    process_logger.info(
        f"Completed {court_type} {year}: {caselaw_count} cases, {section_count} sections"
    )
    return caselaw_count, section_count


def process_unified_caselaw(args):
    """
    Process unified caselaw pipeline that outputs to multiple collections
    """
    # Create both collections if they don't exist
    create_collection_if_none(
        collection_name=CASELAW_COLLECTION,
        schema=get_caselaw_schema(),
        non_interactive=args.non_interactive,
    )
    create_collection_if_none(
        collection_name=CASELAW_SECTION_COLLECTION,
        schema=get_caselaw_section_schema(),
        non_interactive=args.non_interactive,
    )

    # Check if parallel processing is requested
    parallel_workers = getattr(args, "parallel_workers", 1)

    if parallel_workers > 1:
        logger.info(f"Starting parallel processing with {parallel_workers} workers")

        # Generate all year/court combinations
        tasks = []
        for year in args.years:
            for court in args.types:
                tasks.append((year, court.value))

        logger.info(f"Processing {len(tasks)} year/court combinations")

        # Process in parallel
        total_caselaw = 0
        total_sections = 0

        executor = ProcessPoolExecutor(max_workers=parallel_workers)
        try:
            # Submit all tasks
            futures = {}
            for year, court_type in tasks:
                future = executor.submit(
                    process_single_checkpoint, year, court_type, args.limit, args.batch_size
                )
                futures[future] = (year, court_type)

            # Process completed tasks
            for future in as_completed(futures):
                year, court_type = futures[future]
                try:
                    caselaw_count, section_count = future.result()
                    total_caselaw += caselaw_count
                    total_sections += section_count
                    logger.info(
                        f"Completed {court_type} {year}: {caselaw_count} cases, {section_count} sections"
                    )
                except Exception as e:
                    logger.error(f"Failed processing {court_type} {year}: {str(e)}")
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down workers...")
            executor.shutdown(wait=False, cancel_futures=True)  # Python 3.9+ for cancel_futures
            raise
        finally:
            executor.shutdown(wait=True)

        logger.info(
            f"Parallel processing complete: {total_caselaw} cases, {total_sections} sections"
        )

    else:
        # Sequential processing (original implementation)
        documents_iterator = pipe_caselaw_unified
        documents = documents_iterator(**vars(args))

        batch_size = args.batch_size if hasattr(args, "batch_size") else 50
        logger.info(f"Processing unified caselaw with batch size: {batch_size}")

        # Separate batches for each index type
        caselaw_batch = []
        section_batch = []
        caselaw_count = 0
        section_count = 0

        for index_type, doc in documents:
            if index_type == "caselaw":
                caselaw_batch.append(doc)
                caselaw_count += 1
                if len(caselaw_batch) >= batch_size:
                    upload_documents(collection_name=CASELAW_COLLECTION, documents=caselaw_batch)
                    logger.info(
                        f"Uploaded batch of {len(caselaw_batch)} caselaw documents (total: {caselaw_count})"
                    )
                    caselaw_batch = []

            elif index_type == "caselaw-section":
                section_batch.append(doc)
                section_count += 1
                if len(section_batch) >= batch_size:
                    upload_documents(
                        collection_name=CASELAW_SECTION_COLLECTION, documents=section_batch
                    )
                    logger.info(
                        f"Uploaded batch of {len(section_batch)} section documents (total: {section_count})"
                    )
                    section_batch = []

            # Garbage collection after processing batches
            if (caselaw_count + section_count) % (batch_size * 2) == 0:
                import gc

                gc.collect()

        # Upload any remaining documents
        if caselaw_batch:
            upload_documents(collection_name=CASELAW_COLLECTION, documents=caselaw_batch)
            logger.info(
                f"Uploaded final caselaw batch of {len(caselaw_batch)} (total: {caselaw_count})"
            )

        if section_batch:
            upload_documents(collection_name=CASELAW_SECTION_COLLECTION, documents=section_batch)
            logger.info(
                f"Uploaded final section batch of {len(section_batch)} (total: {section_count})"
            )

        logger.info(f"Unified pipeline complete: {caselaw_count} cases, {section_count} sections")


def process_unified_legislation(args):
    """
    Process unified legislation pipeline that outputs to multiple collections.
    """
    # Create both collections if they don't exist
    create_collection_if_none(
        collection_name=LEGISLATION_COLLECTION,
        schema=get_legislation_schema(),
        non_interactive=args.non_interactive,
    )
    create_collection_if_none(
        collection_name=LEGISLATION_SECTION_COLLECTION,
        schema=get_legislation_section_schema(),
        non_interactive=args.non_interactive,
    )

    documents_iterator = pipe_legislation_unified
    documents = documents_iterator(**vars(args))

    batch_size = args.batch_size if hasattr(args, "batch_size") else 50
    logger.info(f"Processing unified legislation with batch size: {batch_size}")

    # Separate batches for each index type
    legislation_batch = []
    section_batch = []
    legislation_count = 0
    section_count = 0

    # Determine embedding fields for legislation metadata
    legislation_embedding_fields = ["title", "description", "type", "year"]

    for index_type, doc in documents:
        if index_type == "legislation":
            legislation_batch.append(doc)
            legislation_count += 1
            if len(legislation_batch) >= batch_size:
                upload_documents(
                    collection_name=LEGISLATION_COLLECTION,
                    documents=legislation_batch,
                    embedding_fields=legislation_embedding_fields,
                )
                logger.info(
                    f"Uploaded batch of {len(legislation_batch)} legislation documents (total: {legislation_count})"
                )
                legislation_batch = []

        elif index_type == "legislation-section":
            section_batch.append(doc)
            section_count += 1
            if len(section_batch) >= batch_size:
                upload_documents(
                    collection_name=LEGISLATION_SECTION_COLLECTION, documents=section_batch
                )
                logger.info(
                    f"Uploaded batch of {len(section_batch)} section documents (total: {section_count})"
                )
                section_batch = []

        # Garbage collection after processing batches
        if (legislation_count + section_count) % (batch_size * 2) == 0:
            import gc

            gc.collect()

    # Upload any remaining documents
    if legislation_batch:
        upload_documents(
            collection_name=LEGISLATION_COLLECTION,
            documents=legislation_batch,
            embedding_fields=legislation_embedding_fields,
        )
        logger.info(
            f"Uploaded final legislation batch of {len(legislation_batch)} (total: {legislation_count})"
        )

    if section_batch:
        upload_documents(collection_name=LEGISLATION_SECTION_COLLECTION, documents=section_batch)
        logger.info(
            f"Uploaded final section batch of {len(section_batch)} (total: {section_count})"
        )

    logger.info(
        f"Unified legislation pipeline complete: {legislation_count} legislation, {section_count} sections"
    )


def process_documents(args):
    """
    Core pipeline logic to process and upload documents
    """
    # Special handling for unified pipelines
    if args.model == "caselaw-unified":
        return process_unified_caselaw(args)

    if args.model == "legislation-unified":
        return process_unified_legislation(args)

    collection, documents_iterator, schema_func = collection_mapping[args.model]

    # Update the collection if provided
    if hasattr(args, "collection") and args.collection:
        collection = args.collection
    else:
        args.collection = collection

    # Create the collection if it does not exist
    create_collection_if_none(
        collection_name=collection,
        schema=schema_func(),
        non_interactive=args.non_interactive,
    )

    # Process documents in batches to reduce memory usage
    documents = documents_iterator(**vars(args))

    # Get batch size from arguments or use default
    batch_size = args.batch_size if hasattr(args, "batch_size") else 50
    logger.info(f"Processing documents with batch size: {batch_size}")

    # Determine embedding fields based on collection type
    embedding_fields = None  # Default: uses "text" field
    if collection == LEGISLATION_COLLECTION:
        # Legislation metadata collection: embed from title + type + description + year
        embedding_fields = ["title", "description", "type", "year"]
    elif collection == AMENDMENT_COLLECTION:
        # Amendment metadata collection: embed from legislation names + type of effect + AI explanation
        embedding_fields = [
            "changed_legislation",
            "affecting_legislation",
            "type_of_effect",
            "changed_provision",
            "affecting_provision",
            "ai_explanation",
        ]

    batch = []
    doc_count = 0

    for doc in documents:
        batch.append(doc)
        doc_count += 1
        if len(batch) >= batch_size:
            upload_documents(
                collection_name=collection, documents=batch, embedding_fields=embedding_fields
            )
            logger.info(f"Uploaded batch of {len(batch)} documents (total: {doc_count})")
            batch = []  # Clear batch after upload

            # Force garbage collection to free memory
            import gc

            gc.collect()

    # Upload any remaining documents
    if batch:
        upload_documents(
            collection_name=collection, documents=batch, embedding_fields=embedding_fields
        )
        logger.info(f"Uploaded final batch of {len(batch)} documents (total: {doc_count})")


def main():
    """
    Unified interface to run the Lex pipeline locally for all document types
    """
    parser = argparse.ArgumentParser(description="Run the Lex Pipeline for any document type")

    # Add model argument with choices from the collection_mapping
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        choices=collection_mapping.keys(),
        required=True,
        help="Model name to process (legislation, legislation-section, caselaw, caselaw-section, caselaw-unified, explanatory-note, amendment)",
    )

    parser.add_argument(
        "-c", "--collection", type=str, default=None, help="Override the default collection name"
    )

    # Add non-interactive flag
    parser.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")

    # Batch size memory management options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of documents to process in each batch",
    )

    # Parallel processing for unified pipeline
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=1,
        help="[Caselaw-unified] Number of parallel workers for processing (default: 1 = sequential)",
    )

    # Legislation types, years, and limit
    parser.add_argument(
        "-t",
        "--types",
        type=str,
        nargs="+",
        default=None,
        help="[Legislation] Legislation types to include",
    )

    parser.add_argument(
        "-y",
        "--years",
        type=str,
        nargs="+",
        default=YEARS,
        help="[Legislation] Legislation years to include. Can be individual years (2020 2021) or ranges (2020-2025)",
    )

    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=None,
        help="Limit number of files to process (default: no limit)",
    )

    parser.add_argument(
        "--from-file",
        action="store_true",
        help="[Legislation] Load documents from file instead of scraping",
    )

    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="[Legislation] Clear the checkpoint file",
    )

    parser.add_argument(
        "--generate-explanations",
        action="store_true",
        help="[Amendment] Generate AI explanations for amendments using GPT-5",
    )

    # Set environment variables for local run
    os.environ["ENVIRONMENT"] = "local"

    # Parse arguments
    args = parser.parse_args()

    # Parse years to handle ranges and individual years
    if hasattr(args, "years") and args.years is not None:
        # Only parse if years were provided (not using default)
        if args.years != YEARS:
            args.years = parse_years(args.years)
        # If using default YEARS, ensure they're integers
        elif isinstance(args.years, list) and args.years and isinstance(args.years[0], str):
            args.years = [int(year) for year in args.years]

    if args.model in ["legislation", "legislation-section", "explanatory-note"]:
        if args.types is None:
            args.types = list(LegislationType)
        else:
            args.types = [LegislationType(t) for t in args.types]
    elif args.model in ["caselaw", "caselaw-section", "caselaw-unified"]:
        if args.types is None:
            args.types = list(Court)
        else:
            args.types = [Court(t) for t in args.types]
    elif args.model == "amendment":
        pass

    # Run the pipeline with error handling
    try:
        logger.info(f"Starting pipeline with model: {args.model}")
        process_documents(args)
        logger.info("Pipeline completed successfully")
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        raise  # Re-raise the exception to maintain the original exit code


if __name__ == "__main__":
    main()
