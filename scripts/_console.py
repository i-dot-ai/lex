"""Shared TUI utilities for Lex scripts.

Provides consistent terminal output across all scripts: coloured logging,
progress bars, headers, and summary tables via the rich library.
"""

import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging with RichHandler for coloured, timestamped output."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
        force=True,
    )


def print_header(
    title: str, *, mode: str | None = None, details: dict[str, str] | None = None
) -> None:
    """Print a consistent script header panel.

    Args:
        title: Script name or purpose.
        mode: Operating mode, e.g. "DRY RUN" or "APPLY".
        details: Key-value pairs to display below the title.
    """
    lines: list[str] = []

    if mode:
        style = "bold yellow" if mode.upper() == "DRY RUN" else "bold green"
        lines.append(f"[{style}]{mode.upper()}[/{style}]")

    if details:
        for key, value in details.items():
            lines.append(f"[dim]{key}:[/dim] {value}")

    subtitle = "\n".join(lines) if lines else None
    panel = Panel(
        subtitle or "",
        title=f"[bold]{title}[/bold]",
        border_style="blue",
        expand=False,
        padding=(0, 2),
    )
    console.print(panel)
    console.print()


def print_summary(title: str, stats: dict[str, int | str], *, success: bool = True) -> None:
    """Print a consistent completion summary table.

    Args:
        title: Summary heading.
        stats: Key-value pairs to display.
        success: Whether the operation succeeded (affects border colour).
    """
    style = "green" if success else "red"
    table = Table(title=title, border_style=style, show_header=False, expand=False, padding=(0, 1))
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    for key, value in stats.items():
        table.add_row(key, str(value))

    console.print()
    console.print(table)
    console.print()
