"""CLI entry point for unified ingestion.

Usage:
    # Daily incremental ingest (current + previous year)
    python -m lex.ingest --mode daily

    # Sample run with limit
    python -m lex.ingest --mode daily --limit 10

    # Full historical ingest
    python -m lex.ingest --mode full

    # Specific years
    python -m lex.ingest --mode full --years 2023 2024
"""

import argparse
import asyncio
import logging
import sys

from lex.ingest.orchestrator import (
    run_amendments_led_ingest,
    run_daily_ingest,
    run_full_ingest,
)


def main() -> int:
    """Main entry point for the ingest CLI."""
    parser = argparse.ArgumentParser(
        description="Unified ingestion pipeline for Lex",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--mode",
        choices=["daily", "full", "amendments-led"],
        default="daily",
        help="Ingest mode: daily (year-based), full (historical), or amendments-led (smart)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items per source (default: unlimited)",
    )

    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        help="Specific years to process (default: auto based on mode)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--pdf-fallback",
        action="store_true",
        help="Enable PDF fallback for legislation without XML content",
    )

    parser.add_argument(
        "--years-back",
        type=int,
        default=2,
        help="Number of years to look back for amendments-led mode (default: 2)",
    )

    parser.add_argument(
        "--enable-summaries",
        action="store_true",
        help="Enable AI summary generation (Stage 2)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Starting ingest: mode={args.mode}, limit={args.limit}")

    try:
        if args.mode == "daily":
            stats = asyncio.run(
                run_daily_ingest(
                    limit=args.limit,
                    enable_pdf_fallback=args.pdf_fallback,
                    enable_summaries=args.enable_summaries,
                )
            )
        elif args.mode == "amendments-led":
            stats = asyncio.run(
                run_amendments_led_ingest(
                    limit=args.limit,
                    enable_pdf_fallback=args.pdf_fallback,
                    years_back=args.years_back,
                )
            )
        else:  # full
            stats = asyncio.run(
                run_full_ingest(
                    years=args.years,
                    limit=args.limit,
                    enable_pdf_fallback=args.pdf_fallback,
                    enable_summaries=args.enable_summaries,
                )
            )

        logger.info(f"Ingest complete: {stats}")
        return 0

    except KeyboardInterrupt:
        logger.info("Ingest interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Ingest failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
