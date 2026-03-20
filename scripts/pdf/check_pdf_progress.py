"""
Check progress of PDF digitisation batch processing.

Usage:
    uv run python scripts/check_pdf_progress.py data/historical_legislation_results.jsonl
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # scripts/ directory

from _console import console, print_header, print_summary, setup_logging
from rich.table import Table


def check_progress(jsonl_path: Path):
    """Check progress statistics from JSONL output file."""

    if not jsonl_path.exists():
        console.print(f"[red]File not found:[/red] {jsonl_path}")
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

    print_header("PDF Processing Progress", details={"File": str(jsonl_path)})

    # Overall progress summary
    print_summary(
        "Overall Progress",
        {
            "Total processed": f"{total:,}",
            "Successful": f"{successful:,} ({successful / total * 100:.1f}%)" if total else "0",
            "Failed": f"{failed:,} ({failed / total * 100:.1f}%)" if total else "0",
        },
        success=failed == 0,
    )

    if successful > 0:
        # Token usage table
        token_table = Table(
            title="Token Usage (Successful Only)",
            border_style="cyan",
            show_header=False,
            expand=False,
            padding=(0, 1),
        )
        token_table.add_column("Metric", style="dim")
        token_table.add_column("Value", justify="right")
        token_table.add_row("Input tokens", f"{total_input_tokens:,}")
        token_table.add_row("Output tokens", f"{total_output_tokens:,}")
        token_table.add_row("Cached tokens", f"{total_cached_tokens:,}")
        token_table.add_row("Total processing time", f"{total_time / 3600:.2f} hours")
        token_table.add_row("Average time per PDF", f"{total_time / successful:.1f}s")
        console.print(token_table)

        # Cost estimate
        input_cost = total_input_tokens / 1_000_000 * 0.15
        output_cost = total_output_tokens / 1_000_000 * 0.60
        cached_cost = total_cached_tokens / 1_000_000 * 0.075
        total_cost = input_cost + output_cost + cached_cost

        print_summary(
            "Cost Estimate (GPT-5-mini)",
            {
                "Input cost": f"${input_cost:.2f}",
                "Output cost": f"${output_cost:.2f}",
                "Cached cost": f"${cached_cost:.2f}",
                "Total cost": f"${total_cost:.2f}",
            },
        )

    if by_type:
        # Breakdown by legislation type
        type_table = Table(
            title="Breakdown by Legislation Type",
            border_style="blue",
            expand=False,
            padding=(0, 1),
        )
        type_table.add_column("Type", style="bold")
        type_table.add_column("Total", justify="right")
        type_table.add_column("Successful", justify="right", style="green")
        type_table.add_column("Success Rate", justify="right")
        type_table.add_column("Failed", justify="right", style="red")

        for leg_type in sorted(by_type.keys()):
            stats = by_type[leg_type]
            success_rate = stats["successful"] / stats["total"] * 100
            type_table.add_row(
                leg_type.upper(),
                f"{stats['total']:,}",
                f"{stats['successful']:,}",
                f"{success_rate:.1f}%",
                f"{stats['failed']:,}",
            )

        console.print()
        console.print(type_table)
        console.print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        console.print("Usage: uv run python scripts/check_pdf_progress.py <jsonl_file>")
        sys.exit(1)

    setup_logging()
    check_progress(Path(sys.argv[1]))
