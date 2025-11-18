"""
Check progress of PDF digitization batch processing.

Usage:
    uv run python scripts/check_pdf_progress.py data/historical_legislation_results.jsonl
"""

import json
import sys
from pathlib import Path


def check_progress(jsonl_path: Path):
    """Check progress statistics from JSONL output file."""

    if not jsonl_path.exists():
        print(f"❌ File not found: {jsonl_path}")
        sys.exit(1)

    total = 0
    successful = 0
    failed = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cached_tokens = 0
    total_time = 0.0

    # Track by type
    by_type = {}

    with open(jsonl_path, "r") as f:
        for line in f:
            if not line.strip():
                continue

            try:
                result = json.loads(line)
                total += 1

                leg_type = result.get("legislation_type", "unknown")
                if leg_type not in by_type:
                    by_type[leg_type] = {"total": 0, "successful": 0, "failed": 0}

                by_type[leg_type]["total"] += 1

                if result.get("success"):
                    successful += 1
                    by_type[leg_type]["successful"] += 1

                    # Extract provenance stats
                    prov = result.get("provenance", {})
                    total_input_tokens += prov.get("input_tokens", 0)
                    total_output_tokens += prov.get("output_tokens", 0)
                    total_cached_tokens += prov.get("cached_tokens", 0)
                    total_time += prov.get("processing_time_seconds", 0.0)
                else:
                    failed += 1
                    by_type[leg_type]["failed"] += 1

            except json.JSONDecodeError:
                continue

    # Print summary
    print(f"\n{'=' * 80}")
    print("PDF DIGITIZATION PROGRESS")
    print(f"{'=' * 80}")
    print(f"File: {jsonl_path}")
    print(f"\nTotal Processed: {total:,}")
    print(f"✅ Successful: {successful:,} ({successful / total * 100:.1f}%)")
    print(f"❌ Failed: {failed:,} ({failed / total * 100:.1f}%)")

    if successful > 0:
        print(f"\n{'=' * 80}")
        print("TOKEN USAGE (Successful Only)")
        print(f"{'=' * 80}")
        print(f"Input Tokens: {total_input_tokens:,}")
        print(f"Output Tokens: {total_output_tokens:,}")
        print(f"Cached Tokens: {total_cached_tokens:,}")
        print(f"\nTotal Processing Time: {total_time / 3600:.2f} hours")
        print(f"Average Time per PDF: {total_time / successful:.1f}s")

        # Cost estimate
        input_cost = total_input_tokens / 1_000_000 * 0.15
        output_cost = total_output_tokens / 1_000_000 * 0.60
        cached_cost = total_cached_tokens / 1_000_000 * 0.075
        total_cost = input_cost + output_cost + cached_cost

        print(f"\n{'=' * 80}")
        print("COST ESTIMATE (GPT-5-mini)")
        print(f"{'=' * 80}")
        print(f"Input Cost: ${input_cost:.2f}")
        print(f"Output Cost: ${output_cost:.2f}")
        print(f"Cached Cost: ${cached_cost:.2f}")
        print(f"Total Cost: ${total_cost:.2f}")

    if by_type:
        print(f"\n{'=' * 80}")
        print("BREAKDOWN BY LEGISLATION TYPE")
        print(f"{'=' * 80}")
        for leg_type in sorted(by_type.keys()):
            stats = by_type[leg_type]
            success_rate = stats["successful"] / stats["total"] * 100
            print(
                f"{leg_type.upper():8s}: {stats['total']:6,} total, {stats['successful']:6,} success ({success_rate:.1f}%), {stats['failed']:6,} failed"
            )

    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/check_pdf_progress.py <jsonl_file>")
        sys.exit(1)

    check_progress(Path(sys.argv[1]))
