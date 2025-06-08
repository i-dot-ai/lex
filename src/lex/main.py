#!/usr/bin/env python
import argparse
import logging
import os
import time
from collections import namedtuple
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from lex.amendment.mappings import amendment_mappings
from lex.amendment.pipeline import pipe_amendments
from lex.caselaw.mappings import caselaw_mappings, caselaw_section_mappings
from lex.caselaw.models import Court
from lex.caselaw.pipeline import pipe_caselaw, pipe_caselaw_sections
from lex.core import create_index_if_none, upload_documents
from lex.core.clients import get_elasticsearch_client
from lex.core.exceptions import RateLimitException
from lex.core.utils import create_inference_endpoint_if_none, set_logging_level
from lex.explanatory_note.mappings import explanatory_note_mappings
from lex.explanatory_note.pipeline import pipe_explanatory_notes
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
        pipe_explanatory_notes,
        explanatory_note_mappings,
    ),
    "amendment": IndexMapping(
        AMENDMENT_INDEX,
        pipe_amendments,
        amendment_mappings,
    ),
}


def parse_years(years_input):
    """
    Parse years input that can contain individual years or ranges.

    Args:
        years_input: List of strings that can be individual years or ranges like "2020-2025"

    Returns:
        List of integers representing all years

    Examples:
        parse_years(["2020", "2022"]) -> [2020, 2022]
        parse_years(["2020-2022"]) -> [2020, 2021, 2022]
        parse_years(["2020-2022", "2025"]) -> [2020, 2021, 2022, 2025]
    """
    if years_input is None:
        return None

    all_years = []

    for year_item in years_input:
        year_str = str(year_item)

        if "-" in year_str:
            # Handle range like "2020-2025"
            try:
                start_year, end_year = year_str.split("-")
                start_year = int(start_year)
                end_year = int(end_year)

                if start_year > end_year:
                    raise ValueError(
                        f"Invalid year range: {year_str}. Start year must be <= end year."
                    )

                # Generate all years in the range (inclusive)
                range_years = list(range(start_year, end_year + 1))
                all_years.extend(range_years)

            except ValueError as e:
                if "Invalid year range" in str(e):
                    raise e
                else:
                    raise ValueError(
                        f"Invalid year range format: {year_str}. Use format like '2020-2025'."
                    )
        else:
            # Handle individual year
            try:
                all_years.append(int(year_str))
            except ValueError:
                raise ValueError(f"Invalid year: {year_str}. Must be a valid integer.")

    # Remove duplicates and sort
    return sorted(list(set(all_years)))


def process_documents(args):
    """
    Core pipeline logic to process and upload documents
    """
    start_time = time.time()
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
    # Add checkpoint-specific parameters if applicable
    pipeline_args = vars(args)
    if args.model in ["caselaw", "caselaw-section"]:
        pipeline_args.update({
            "use_checkpoint": not args.no_checkpoint,
            "clear_checkpoint": args.clear_checkpoint,
        })
    
    documents = documents_iterator(**pipeline_args)

    # Get batch size from arguments or use default
    batch_size = args.batch_size if hasattr(args, "batch_size") else 50
    logger.info(f"Processing documents with batch size: {batch_size}")

    batch = []
    doc_count = 0
    last_progress_update = time.time()
    progress_interval = 300  # Log progress every 5 minutes
    
    # Track statistics
    success_count = 0
    error_count = 0
    consecutive_rate_limits = 0
    # Allow many more rate limit retries for overnight runs
    max_consecutive_rate_limits = 50  # Increased from 3

    try:
        for doc in documents:
            try:
                batch.append(doc)
                doc_count += 1
                consecutive_rate_limits = 0  # Reset on success
                
                # Simple progress logging every N documents and every M minutes
                current_time = time.time()
                if doc_count % 1000 == 0 or (current_time - last_progress_update) > progress_interval:
                    elapsed = current_time - start_time
                    rate = doc_count / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Progress update: {doc_count} documents processed "
                        f"({rate:.1f} docs/second, {elapsed/60:.1f} minutes elapsed)"
                    )
                    last_progress_update = current_time
                
                if len(batch) >= batch_size:
                    upload_result = upload_documents(index_name=index, documents=batch)
                    # Assume upload_documents returns success count or we count batch size as success
                    success_count += len(batch)
                    
                    logger.info(f"Uploaded batch of {len(batch)} documents (total: {doc_count})")
                    batch = []  # Clear batch after upload

                    # Force garbage collection to free memory
                    import gc
                    gc.collect()
                    
            except RateLimitException as e:
                consecutive_rate_limits += 1
                
                # Save any pending batch before potentially exiting
                if batch:
                    logger.info(f"Saving batch of {len(batch)} documents before handling rate limit")
                    upload_documents(index_name=index, documents=batch)
                    success_count += len(batch)
                    batch = []
                
                if consecutive_rate_limits >= max_consecutive_rate_limits:
                    logger.error(
                        f"Hit rate limit {consecutive_rate_limits} times consecutively. "
                        f"Stopping pipeline gracefully. Progress saved at {doc_count} documents.",
                        extra={
                            "doc_count": doc_count,
                            "success_count": success_count,
                            "model": args.model,
                            "rate_limit_count": consecutive_rate_limits
                        }
                    )
                    # Exit gracefully - checkpoint already saved by scraper
                    break
                else:
                    # Use retry_after if available, otherwise exponential backoff
                    retry_after = getattr(e, 'retry_after', None)
                    if retry_after:
                        wait_time = int(retry_after) + 10  # Add 10s buffer
                    else:
                        # Exponential backoff: 30s, 60s, 120s, 240s, 480s (max 8 min)
                        wait_time = min(30 * (2 ** (consecutive_rate_limits - 1)), 480)
                    
                    logger.info(
                        f"Rate limited (attempt {consecutive_rate_limits}/{max_consecutive_rate_limits}). "
                        f"Waiting {wait_time}s before continuing...",
                        extra={
                            "wait_time": wait_time,
                            "consecutive_attempts": consecutive_rate_limits,
                            "retry_after": retry_after
                        }
                    )
                    time.sleep(wait_time)
                    
    except Exception as e:
        # Handle any other exceptions
        logger.error(f"Pipeline error: {e}", exc_info=True)
        # Try to save any pending batch
        if batch:
            try:
                upload_documents(index_name=index, documents=batch)
                success_count += len(batch)
            except:
                pass
        raise
        
    finally:
        # Upload any remaining documents
        if batch:
            upload_result = upload_documents(index_name=index, documents=batch)
            success_count += len(batch)
            logger.info(f"Uploaded final batch of {len(batch)} documents (total: {doc_count})")
    # Final summary
    elapsed_time = time.time() - start_time
    
    # Create detailed summary
    summary_extra = {
        "model": args.model,
        "total_documents": doc_count,
        "successful_uploads": success_count,
        "duration_seconds": elapsed_time,
        "duration_minutes": elapsed_time / 60,
        "avg_docs_per_second": doc_count / elapsed_time if elapsed_time > 0 else 0,
        "final_status": "completed" if consecutive_rate_limits < max_consecutive_rate_limits else "rate_limited"
    }
    
    # Add additional context if available
    if hasattr(args, "years") and args.years:
        summary_extra["year_range"] = f"{min(args.years)}-{max(args.years)}"
    if hasattr(args, "types") and args.types:
        summary_extra["document_types"] = len(args.types)
    
    logger.info(
        f"Pipeline processing complete for {args.model}: "
        f"{doc_count} documents processed in {elapsed_time/60:.1f} minutes "
        f"({doc_count/elapsed_time:.1f} docs/second average)",
        extra=summary_extra
    )


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
        help="Model name to process (caselaw, caselaw-section, legislation, legislation-section, explanatory-note, amendment)",
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
        help="[Legislation] Limit number of files to process (default: no limit)",
    )

    parser.add_argument(
        "--from-file",
        action="store_true",
        help="[Legislation] Load documents from file instead of scraping",
    )
    
    # Checkpoint management arguments
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint if available (default: true)",
    )
    
    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Disable checkpoint functionality",
    )
    
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Clear existing checkpoint and start fresh",
    )
    
    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="List all available checkpoints and exit",
    )

    # Set environment variables for local run
    os.environ["ENVIRONMENT"] = "local"

    # Parse arguments
    args = parser.parse_args()
    
    # Handle checkpoint listing
    if args.list_checkpoints:
        from lex.core.checkpoint import PipelineCheckpoint
        checkpoints = PipelineCheckpoint.list_checkpoints()
        if checkpoints:
            print("Available checkpoints:")
            for cp in sorted(checkpoints):
                print(f"  - {cp}")
        else:
            print("No checkpoints found.")
        return

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
    elif args.model in ["caselaw", "caselaw-section"]:
        if args.types is not None:
            args.types = [Court(t) for t in args.types]
    elif args.model == "amendment":
        pass

    # Run the pipeline with error handling
    try:
        # Log comprehensive pipeline start information
        start_timestamp = datetime.now().isoformat()
        
        # Build parameter summary
        params = {
            "model": args.model,
            "timestamp": start_timestamp,
            "batch_size": getattr(args, "batch_size", 50),
            "non_interactive": getattr(args, "non_interactive", False),
            "index": getattr(args, "index", index_mapping[args.model].index)
        }
        
        # Add model-specific parameters
        if hasattr(args, "years") and args.years:
            params["years"] = f"{min(args.years)}-{max(args.years)}" if args.years else "all"
            params["year_count"] = len(args.years)
        
        if hasattr(args, "types") and args.types:
            params["types"] = [str(t.value) if hasattr(t, 'value') else str(t) for t in args.types]
            params["type_count"] = len(args.types)
        
        if hasattr(args, "limit"):
            params["limit"] = args.limit if args.limit else "unlimited"
        
        logger.info(
            f"Pipeline starting: {args.model} processing",
            extra={"pipeline_params": params}
        )
        
        # Also log as formatted string for readability
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        logger.info(f"Pipeline parameters: {param_str}")
        
        process_documents(args)
        
        end_timestamp = datetime.now().isoformat()
        duration = (datetime.fromisoformat(end_timestamp) - datetime.fromisoformat(start_timestamp)).total_seconds()
        
        logger.info(
            f"Pipeline completed successfully",
            extra={
                "model": args.model,
                "start_time": start_timestamp,
                "end_time": end_timestamp,
                "duration_seconds": duration,
                "duration_minutes": duration / 60
            }
        )
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        raise  # Re-raise the exception to maintain the original exit code


if __name__ == "__main__":
    main()
