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

sys.path.insert(0, str(Path(__file__).parent.parent))  # scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from _console import console, print_header, print_summary, setup_logging

from lex.processing.historical_pdf.batch import process_pdf_batch_from_csv, process_single_pdf

# Load environment variables
load_dotenv(override=True)

# Configure logging
setup_logging()
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
        help="Process all PDFs from CSV file (columns: pdf_url, legislation_type, identifier)",
    )
    parser.add_argument("--url", help="Process single PDF from URL")
    parser.add_argument(
        "--type", dest="legislation_type", help="Legislation type (e.g., ukpga, aep, ukla)"
    )
    parser.add_argument("--id", dest="identifier", help="Identifier (e.g., Edw7/6/19, Geo3/41/90)")

    # Options
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Maximum concurrent PDF processing (default: 10)",
    )
    parser.add_argument("--output", type=Path, help="Output file for results (JSONL format)")

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
            print_header(
                "Batch PDF Processing",
                details={
                    "CSV": str(args.csv),
                    "Max concurrent": str(args.max_concurrent),
                    "Output": str(args.output) if args.output else "(none - results logged only)",
                },
            )

            # Open output file if specified (append mode for resume capability)
            output_file = None
            if args.output:
                output_file = open(args.output, "a")

            processed = 0
            successful = 0
            failed = 0

            async for result in process_pdf_batch_from_csv(
                args.csv, max_concurrent=args.max_concurrent, output_path=args.output
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

            print_summary(
                "Batch Complete",
                {
                    "Processed": processed,
                    "Successful": successful,
                    "Failed": failed,
                },
                success=failed == 0,
            )

        else:
            # Single PDF processing
            print_header(
                "Single PDF Processing",
                details={
                    "Type": args.legislation_type,
                    "Identifier": args.identifier,
                    "URL": args.url,
                },
            )

            result = await process_single_pdf(args.url, args.legislation_type, args.identifier)

            print_summary(
                "Results",
                {
                    "Success": str(result.success),
                    "Model": result.provenance.model,
                    "Input tokens": f"{result.provenance.input_tokens:,}",
                    "Output tokens": f"{result.provenance.output_tokens:,}",
                    "Cached tokens": f"{result.provenance.cached_tokens:,}",
                    "Processing time": f"{result.provenance.processing_time_seconds:.1f}s",
                    "Extracted length": f"{len(result.extracted_data):,} chars",
                },
                success=result.success,
            )

            if result.success:
                console.print("\n[bold]Extracted Data (first 500 chars):[/bold]")
                console.print("-" * 80)
                preview = (
                    result.extracted_data[:500] + "..."
                    if len(result.extracted_data) > 500
                    else result.extracted_data
                )
                console.print(preview)
            else:
                console.print(f"\n[red]Error:[/red] {result.error}")

            # Write to output if specified
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(result.model_dump(), f, default=str, indent=2)
                console.print(f"\nResults written to: {args.output}")

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
