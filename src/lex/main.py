#!/usr/bin/env python
import argparse
import logging
import os
from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple

from dotenv import load_dotenv

load_dotenv()

from lex.amendment.mappings import amendment_mappings
from lex.amendment.pipeline import pipe_amendments
from lex.caselaw.mappings import caselaw_mappings, caselaw_section_mappings
from lex.caselaw.models import Court
from lex.caselaw.pipeline import pipe_caselaw, pipe_caselaw_sections, pipe_caselaw_unified
from lex.core import create_index_if_none, upload_documents
from lex.core.clients import get_elasticsearch_client
from lex.core.utils import create_inference_endpoint_if_none, parse_years, set_logging_level
from lex.explanatory_note.mappings import explanatory_note_mappings
from lex.explanatory_note.pipeline import pipe_explanatory_note
from lex.legislation.mappings import legislation_mappings, legislation_section_mappings
from lex.legislation.models import LegislationType
from lex.legislation.pipeline import pipe_legislation, pipe_legislation_sections
from lex.settings import (
    AMENDMENT_INDEX,
    CASELAW_INDEX,
    CASELAW_SECTION_INDEX,
    EXPLANATORY_NOTE_INDEX,
    INFERENCE_ID,
    LEGISLATION_INDEX,
    LEGISLATION_SECTION_INDEX,
    YEARS,
)

# Environment settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "localhost")
LOGS_INDEX = os.getenv("ELASTIC_LOGS_INDEX_PIPELINE", "logs-pipeline")

# Initialize Elasticsearch client
es_client = get_elasticsearch_client()

# Set up logging with Elasticsearch
set_logging_level(
    logging.INFO,
    elastic_client=es_client,
    elastic_index=LOGS_INDEX,
    service_name="pipeline",
    environment=ENVIRONMENT,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Mapping of model to index name, document iterator, model class, and alternative text generator
IndexMapping = namedtuple("IndexMapping", ["index", "pipe", "mappings"])

index_mapping = {
    "caselaw": IndexMapping(
        CASELAW_INDEX,
        pipe_caselaw,
        caselaw_mappings,
    ),
    "caselaw-section": IndexMapping(
        CASELAW_SECTION_INDEX,
        pipe_caselaw_sections,
        caselaw_section_mappings,
    ),
    "caselaw-unified": IndexMapping(
        None,  # Special case - uses multiple indices
        pipe_caselaw_unified,
        None,  # Mappings handled per index type
    ),
    "legislation": IndexMapping(
        LEGISLATION_INDEX,
        pipe_legislation,
        legislation_mappings,
    ),
    "legislation-section": IndexMapping(
        LEGISLATION_SECTION_INDEX,
        pipe_legislation_sections,
        legislation_section_mappings,
    ),
    "explanatory-note": IndexMapping(
        EXPLANATORY_NOTE_INDEX,
        pipe_explanatory_note,
        explanatory_note_mappings,
    ),
    "amendment": IndexMapping(
        AMENDMENT_INDEX,
        pipe_amendments,
        amendment_mappings,
    ),
}


def process_single_checkpoint(year: int, court_type: str, limit: int = None, batch_size: int = 50) -> Tuple[int, int]:
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
                upload_documents(index_name=CASELAW_INDEX, documents=caselaw_batch)
                caselaw_batch = []
                
        elif index_type == "caselaw-section":
            section_batch.append(doc)
            section_count += 1
            if len(section_batch) >= batch_size:
                upload_documents(index_name=CASELAW_SECTION_INDEX, documents=section_batch)
                section_batch = []
    
    # Upload remaining batches
    if caselaw_batch:
        upload_documents(index_name=CASELAW_INDEX, documents=caselaw_batch)
    if section_batch:
        upload_documents(index_name=CASELAW_SECTION_INDEX, documents=section_batch)
    
    process_logger.info(f"Completed {court_type} {year}: {caselaw_count} cases, {section_count} sections")
    return caselaw_count, section_count


def process_unified_caselaw(args):
    """
    Process unified caselaw pipeline that outputs to multiple indices
    """
    # Create both indices if they don't exist
    create_index_if_none(index_name=CASELAW_INDEX, non_interactive=args.non_interactive, mappings=caselaw_mappings)
    create_index_if_none(index_name=CASELAW_SECTION_INDEX, non_interactive=args.non_interactive, mappings=caselaw_section_mappings)
    
    # Create the inference endpoint if it doesn't exist
    create_inference_endpoint_if_none(inference_id=INFERENCE_ID)
    
    # Check if parallel processing is requested
    parallel_workers = getattr(args, 'parallel_workers', 1)
    
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
                future = executor.submit(process_single_checkpoint, year, court_type, args.limit, args.batch_size)
                futures[future] = (year, court_type)
            
            # Process completed tasks
            for future in as_completed(futures):
                year, court_type = futures[future]
                try:
                    caselaw_count, section_count = future.result()
                    total_caselaw += caselaw_count
                    total_sections += section_count
                    logger.info(f"Completed {court_type} {year}: {caselaw_count} cases, {section_count} sections")
                except Exception as e:
                    logger.error(f"Failed processing {court_type} {year}: {str(e)}")
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down workers...")
            executor.shutdown(wait=False, cancel_futures=True)  # Python 3.9+ for cancel_futures
            raise
        finally:
            executor.shutdown(wait=True)
        
        logger.info(f"Parallel processing complete: {total_caselaw} cases, {total_sections} sections")
        
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
                    upload_documents(index_name=CASELAW_INDEX, documents=caselaw_batch)
                    logger.info(f"Uploaded batch of {len(caselaw_batch)} caselaw documents (total: {caselaw_count})")
                    caselaw_batch = []
                    
            elif index_type == "caselaw-section":
                section_batch.append(doc)
                section_count += 1
                if len(section_batch) >= batch_size:
                    upload_documents(index_name=CASELAW_SECTION_INDEX, documents=section_batch)
                    logger.info(f"Uploaded batch of {len(section_batch)} section documents (total: {section_count})")
                    section_batch = []
            
            # Garbage collection after processing batches
            if (caselaw_count + section_count) % (batch_size * 2) == 0:
                import gc
                gc.collect()
        
        # Upload any remaining documents
        if caselaw_batch:
            upload_documents(index_name=CASELAW_INDEX, documents=caselaw_batch)
            logger.info(f"Uploaded final caselaw batch of {len(caselaw_batch)} (total: {caselaw_count})")
        
        if section_batch:
            upload_documents(index_name=CASELAW_SECTION_INDEX, documents=section_batch)
            logger.info(f"Uploaded final section batch of {len(section_batch)} (total: {section_count})")
        
        logger.info(f"Unified pipeline complete: {caselaw_count} cases, {section_count} sections")


def process_documents(args):
    """
    Core pipeline logic to process and upload documents
    """
    # Special handling for unified pipeline
    if args.model == "caselaw-unified":
        return process_unified_caselaw(args)
    
    index, documents_iterator, mappings = index_mapping[args.model]

    # Update the index if provided
    if args.index:
        index = args.index
    else:
        args.index = index

    # Create the index if it does not exist
    create_index_if_none(index_name=index, non_interactive=args.non_interactive, mappings=mappings)

    # Create the inference endpoint if it doesn't exist
    create_inference_endpoint_if_none(inference_id=INFERENCE_ID)

    # Process documents in batches to reduce memory usage
    documents = documents_iterator(**vars(args))

    # Get batch size from arguments or use default
    batch_size = args.batch_size if hasattr(args, "batch_size") else 50
    logger.info(f"Processing documents with batch size: {batch_size}")

    batch = []
    doc_count = 0

    for doc in documents:
        batch.append(doc)
        doc_count += 1
        if len(batch) >= batch_size:
            upload_documents(index_name=index, documents=batch)
            logger.info(f"Uploaded batch of {len(batch)} documents (total: {doc_count})")
            batch = []  # Clear batch after upload

            # Force garbage collection to free memory
            import gc

            gc.collect()

    # Upload any remaining documents
    if batch:
        upload_documents(index_name=index, documents=batch)
        logger.info(f"Uploaded final batch of {len(batch)} documents (total: {doc_count})")


def main():
    """
    Unified interface to run the Lex pipeline locally for all document types
    """
    parser = argparse.ArgumentParser(description="Run the Lex Pipeline for any document type")

    # Add model argument with choices from the index_mapping
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        choices=index_mapping.keys(),
        required=True,
        help="Model name to process (caselaw, caselaw-section, caselaw-unified, legislation, legislation-section, explanatory-note, amendment)",
    )

    parser.add_argument(
        "-i", "--index", type=str, default=None, help="Override the default index name"
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
