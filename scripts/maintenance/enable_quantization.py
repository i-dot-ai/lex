#!/usr/bin/env python
"""Enable scalar quantisation on Qdrant collections for improved performance.

This script enables INT8 scalar quantisation which:
- Reduces memory usage by 75% (4 bytes -> 1 byte per dimension)
- Speeds up search by 20-30% (fewer memory bus transfers)
- Maintains <1% accuracy loss (Qdrant rescores with original vectors)

The optimisation process runs in the background and may take 10-30 minutes
depending on collection size.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))  # scripts/ directory

from dotenv import load_dotenv

load_dotenv()

from _console import console, print_header, print_summary, setup_logging
from qdrant_client import QdrantClient
from qdrant_client.models import ScalarQuantization, ScalarQuantizationConfig, ScalarType
from rich.table import Table

from lex.core.qdrant_client import get_qdrant_client

logger = logging.getLogger(__name__)

COLLECTIONS = [
    "legislation",
    "legislation_section",
    "caselaw",
    "caselaw_section",
    "amendment",
    "explanatory_note",
]


def enable_quantization(client: QdrantClient, collection_name: str):
    """Enable scalar quantisation on a collection."""
    try:
        logger.info(f"Enabling INT8 quantisation for {collection_name}...")

        client.update_collection(
            collection_name=collection_name,
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            ),
        )

        logger.info(f"Quantisation enabled for {collection_name}")

    except Exception as e:
        logger.error(f"Failed to enable quantisation for {collection_name}: {e}")
        raise


def check_collection_status(client: QdrantClient, collection_name: str) -> tuple[str, str, bool]:
    """Check optimisation status of a collection. Returns (status, optimiser, is_ready)."""
    try:
        info = client.get_collection(collection_name)
        status = str(info.status)
        optimizer_status = str(info.optimizer_status)
        is_ready = status == "green"
        return status, optimizer_status, is_ready
    except Exception as e:
        logger.error(f"Failed to check status for {collection_name}: {e}")
        return "error", str(e), False


def main():
    """Enable quantisation on all configured collections."""
    setup_logging()

    print_header(
        "Enable Quantisation",
        details={
            "Collections": ", ".join(COLLECTIONS),
            "Type": "INT8 scalar quantisation",
        },
    )

    client = get_qdrant_client()

    enabled = 0
    failed = 0

    for collection in COLLECTIONS:
        try:
            enable_quantization(client, collection)
            enabled += 1
        except Exception as e:
            logger.error(f"Failed to process {collection}: {e}")
            failed += 1

    # Build status table
    table = Table(
        title="Collection Status",
        border_style="blue",
        show_header=True,
        expand=False,
        padding=(0, 1),
    )
    table.add_column("Collection", style="bold")
    table.add_column("Status")
    table.add_column("Optimiser")
    table.add_column("Ready")

    for collection in COLLECTIONS:
        status, optimizer_status, is_ready = check_collection_status(client, collection)
        ready_text = "[green]yes[/green]" if is_ready else "[yellow]optimising[/yellow]"
        table.add_row(collection, status, optimizer_status, ready_text)

    console.print()
    console.print(table)

    print_summary(
        "Quantisation Results",
        {
            "Enabled": enabled,
            "Failed": failed,
            "Expected memory reduction": "75%",
            "Expected search speedup": "20-30%",
            "Expected accuracy loss": "<1%",
        },
        success=failed == 0,
    )


if __name__ == "__main__":
    main()
