"""
CLI for processing historical UK legislation PDFs with Azure OpenAI.

Usage:
    # Process single PDF
    uv run python scripts/process_pdfs.py --url "..." --type ukpga --id Edw7/6/19

    # Process batch from CSV
    uv run python scripts/process_pdfs.py --csv data/pdf_only_legislation_complete.csv --max-concurrent 5
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from lex.pdf_digitization.batch import process_pdf_batch_from_csv, process_single_pdf

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Process historical UK legislation PDFs with Azure OpenAI OCR"
    )

    # Command selection
    parser.add_argument(
        "--csv",
        type=Path,
        help="Process all PDFs from CSV file (columns: pdf_url, legislation_type, identifier)"
    )
    parser.add_argument(
        "--url",
        help="Process single PDF from URL"
    )
    parser.add_argument(
        "--type",
        dest="legislation_type",
        help="Legislation type (e.g., ukpga, aep, ukla)"
    )
    parser.add_argument(
        "--id",
        dest="identifier",
        help="Identifier (e.g., Edw7/6/19, Geo3/41/90)"
    )

    # Options
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Maximum concurrent PDF processing (default: 10)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for results (JSONL format)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.csv and (args.url or args.legislation_type or args.identifier):
        parser.error("Cannot specify both --csv and single PDF options (--url, --type, --id)")

    if args.url and not (args.legislation_type and args.identifier):
        parser.error("--url requires both --type and --id")

    if not args.csv and not args.url:
        parser.error("Must specify either --csv or --url")

    try:
        if args.csv:
            # Batch processing from CSV
            print(f"\n{'='*80}")
            print(f"BATCH PDF PROCESSING")
            print(f"{'='*80}")
            print(f"CSV: {args.csv}")
            print(f"Max Concurrent: {args.max_concurrent}")
            print(f"Output: {args.output or '(none - results logged only)'}")
            print(f"{'='*80}\n")

            # Open output file if specified (append mode for resume capability)
            output_file = None
            if args.output:
                output_file = open(args.output, 'a')

            processed = 0
            successful = 0
            failed = 0

            async for result in process_pdf_batch_from_csv(
                args.csv,
                max_concurrent=args.max_concurrent,
                output_path=args.output
            ):
                processed += 1

                if result.success:
                    successful += 1
                else:
                    failed += 1

                # Write to output file if specified
                if output_file:
                    output_file.write(json.dumps(result.model_dump(), default=str) + "\n")
                    output_file.flush()

                # Log summary
                if processed % 10 == 0:
                    logger.info(
                        f"Progress: {processed} processed, {successful} successful, {failed} failed"
                    )

            if output_file:
                output_file.close()

            print(f"\n{'='*80}")
            print(f"BATCH COMPLETE")
            print(f"{'='*80}")
            print(f"Processed: {processed}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print(f"{'='*80}\n")

        else:
            # Single PDF processing
            print(f"\n{'='*80}")
            print(f"SINGLE PDF PROCESSING")
            print(f"{'='*80}")
            print(f"Type: {args.legislation_type}")
            print(f"Identifier: {args.identifier}")
            print(f"URL: {args.url}")
            print(f"{'='*80}\n")

            result = await process_single_pdf(
                args.url,
                args.legislation_type,
                args.identifier
            )

            print(f"\n{'='*80}")
            print(f"RESULTS")
            print(f"{'='*80}")
            print(f"Success: {result.success}")
            print(f"Model: {result.provenance.model}")
            print(f"Input Tokens: {result.provenance.input_tokens:,}")
            print(f"Output Tokens: {result.provenance.output_tokens:,}")
            print(f"Cached Tokens: {result.provenance.cached_tokens:,}")
            print(f"Processing Time: {result.provenance.processing_time_seconds:.1f}s")
            print(f"Extracted Length: {len(result.extracted_data):,} chars")

            if result.success:
                print(f"\nExtracted Data (first 500 chars):")
                print(f"-" * 80)
                print(result.extracted_data[:500] + "..." if len(result.extracted_data) > 500 else result.extracted_data)
            else:
                print(f"\nError: {result.error}")

            print(f"{'='*80}\n")

            # Write to output if specified
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result.model_dump(), f, default=str, indent=2)
                print(f"Results written to: {args.output}\n")

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
