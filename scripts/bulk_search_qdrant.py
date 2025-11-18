#!/usr/bin/env python3
"""
Bulk semantic search of UK legislation sections from Qdrant vector database.

Export legislation search results to CSV, Excel, and JSON formats with relevance scores.
Uses hybrid search (dense semantic + sparse BM25) for best results.

Example usage:
    # Semantic search for environmental reporting
    python lex_bulk_query.py --query "environmental reporting requirements" --limit 100

    # Filter by year range
    python lex_bulk_query.py --query "data protection" --year-from 2010 --year-to 2024 --limit 200

    # Search legislation sections (default)
    python lex_bulk_query.py --query "waste regulations" --collection legislation_section --limit 500

    # Search full legislation documents
    python lex_bulk_query.py --query "climate change" --collection legislation --limit 50

Requirements:
    pip install qdrant-client pandas openpyxl rich fastembed

    # Azure OpenAI credentials required (for embeddings):
    export AZURE_OPENAI_API_KEY=your_key
    export AZURE_OPENAI_ENDPOINT=your_endpoint
    export AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    Prefetch,
    Range,
)
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add src to path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent / "Code" / "lex"
if project_root.exists():
    sys.path.insert(0, str(project_root / "src"))

try:
    from lex.core.embeddings import generate_hybrid_embeddings
except ImportError:
    print("ERROR: Could not import lex.core.embeddings")
    print("Make sure you're running from a location where /Users/liam/Code/lex/src is accessible")
    print("Or set PYTHONPATH=/Users/liam/Code/lex/src")
    sys.exit(1)

console = Console()


def create_qdrant_client(cloud_url: str, api_key: str) -> QdrantClient:
    """Create and return Qdrant client."""
    return QdrantClient(url=cloud_url, api_key=api_key, timeout=60)


def build_filters(
    year_from: Optional[int], year_to: Optional[int], types: Optional[List[str]]
) -> Optional[Filter]:
    """Build Qdrant filters for year range and legislation types."""
    conditions = []

    # Year filter (for legislation_section, filter by legislation_year)
    if year_from or year_to:
        range_filter = {}
        if year_from:
            range_filter["gte"] = year_from
        if year_to:
            range_filter["lte"] = year_to
        # Try both year (for legislation collection) and legislation_year (for section collection)
        conditions.append(FieldCondition(key="legislation_year", range=Range(**range_filter)))

    # Type filter (for legislation_section, filter by legislation_type)
    if types:
        for leg_type in types:
            conditions.append(FieldCondition(key="legislation_type", match={"value": leg_type}))

    return Filter(must=conditions) if conditions else None


def semantic_search(
    client: QdrantClient,
    collection_name: str,
    query: str,
    limit: int,
    filters: Optional[Filter] = None,
) -> List[Dict[str, Any]]:
    """
    Perform semantic search using hybrid embeddings (dense + sparse).

    Returns results with scores and all fields including text content.
    """
    console.print("\n[cyan]Performing semantic search...[/cyan]")
    console.print(f"[cyan]Query:[/cyan] {query}")
    console.print(f"[cyan]Collection:[/cyan] {collection_name}")
    console.print(f"[cyan]Limit:[/cyan] {limit}")

    # Generate hybrid embeddings (dense + sparse)
    console.print("[yellow]Generating embeddings...[/yellow]")
    dense, sparse = generate_hybrid_embeddings(query)

    # Hybrid search with DBSF fusion
    dense_limit = max(30, 3 * limit)
    sparse_limit = max(8, int(0.8 * limit))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Searching {collection_name}...", total=None)

        results = client.query_points(
            collection_name=collection_name,
            query=FusionQuery(fusion=Fusion.DBSF),  # Distribution-Based Score Fusion
            prefetch=[
                Prefetch(query=dense, using="dense", limit=dense_limit),
                Prefetch(query=sparse, using="sparse", limit=sparse_limit),
            ],
            query_filter=filters,
            limit=limit,
            with_payload=True,  # Get all fields including text
        )

        progress.update(task, completed=True)

    # Extract results with scores
    output = []
    max_score = max([p.score for p in results.points], default=1.0) if results.points else 1.0

    for point in results.points:
        # Normalize score to 0-100 range
        normalized_score = (point.score / max_score) * 100 if max_score > 0 else 0

        # Extract text field (handle nested dict if present)
        text_field = point.payload.get("text", "")
        if isinstance(text_field, dict):
            # Text might be nested as {'text': 'actual content'}
            text_field = text_field.get("text", "")

        result = {
            "score": round(normalized_score, 2),
            "id": point.payload.get("id"),
            "uri": point.payload.get("uri"),
            "title": point.payload.get("title"),
            "text": text_field,  # Section content
            "legislation_id": point.payload.get("legislation_id", ""),
            "legislation_type": point.payload.get("legislation_type", ""),
            "legislation_year": point.payload.get("legislation_year", ""),
            "provision_type": point.payload.get("provision_type", ""),
            "number": point.payload.get("number"),
            # For legislation collection (not sections)
            "description": point.payload.get("description", ""),
            "type": point.payload.get("type", ""),
            "category": point.payload.get("category", ""),
            "year": point.payload.get("year", ""),
            "status": point.payload.get("status", ""),
            "enactment_date": point.payload.get("enactment_date", ""),
        }
        output.append(result)

    console.print(f"[green]✓[/green] Found {len(output)} results")
    return output


def export_results(
    results: List[Dict[str, Any]],
    query: str,
    formats: List[str],
    output_dir: Optional[Path] = None,
):
    """Export results to CSV, Excel, and JSON."""
    if not results:
        console.print("[yellow]⚠[/yellow] No results to export")
        return

    # Create timestamp-based output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_dir is None:
        output_dir = Path(f"./lex_exports_{timestamp}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate safe filename from query
    safe_query = "".join(c if c.isalnum() else "_" for c in query)[:50]
    base_filename = f"search_{safe_query}_{timestamp}"

    # Convert to DataFrame
    df = pd.DataFrame(results)

    console.print(f"\n[cyan]Exporting {len(results)} results to {output_dir}...[/cyan]")

    # CSV
    if "csv" in formats:
        csv_path = output_dir / f"{base_filename}.csv"
        df.to_csv(csv_path, index=False)
        console.print(f"[green]✓[/green] CSV: {csv_path}")

    # Excel
    if "excel" in formats:
        excel_path = output_dir / f"{base_filename}.xlsx"
        df.to_excel(excel_path, index=False, engine="openpyxl")
        console.print(f"[green]✓[/green] Excel: {excel_path}")

    # JSON
    if "json" in formats:
        json_path = output_dir / f"{base_filename}.json"
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        console.print(f"[green]✓[/green] JSON: {json_path}")


def display_results_table(results: List[Dict[str, Any]], max_rows: int = 10):
    """Display results in a rich table."""
    if not results:
        return

    table = Table(title=f"\n🔍 Top {min(max_rows, len(results))} Results", show_lines=True)

    table.add_column("Score", justify="right", style="green", width=8)
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Type", style="cyan", width=12)
    table.add_column("Year", justify="right", style="magenta", width=6)
    table.add_column("Text Preview", style="dim", max_width=40)

    for result in results[:max_rows]:
        # Safely extract fields (handle empty strings and non-string types)
        text = str(result.get("text", ""))
        text_preview = text[:100] + "..." if len(text) > 100 else text

        title = str(result.get("title", ""))
        title_display = title[:50] + "..." if len(title) > 50 else title

        # Get year from either legislation_year or year field
        year = result.get("legislation_year") or result.get("year") or ""
        leg_type = result.get("legislation_type") or result.get("type") or ""

        table.add_row(
            f"{result['score']:.1f}",
            title_display,
            str(leg_type) if leg_type else "",
            str(year) if year else "",
            text_preview,
        )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="Semantic search UK legislation from Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic semantic search
  python lex_bulk_query.py --query "environmental reporting requirements" --limit 100

  # Filter by year range
  python lex_bulk_query.py --query "data protection" --year-from 2010 --year-to 2024

  # Search legislation sections (default)
  python lex_bulk_query.py --query "waste regulations" --collection legislation_section

  # Search full legislation documents
  python lex_bulk_query.py --query "climate change" --collection legislation --limit 50

  # Filter by legislation type
  python lex_bulk_query.py --query "environmental" --types ukpga uksi --limit 200
        """,
    )

    # Required query
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Search query (semantic search using hybrid embeddings)",
    )

    # Qdrant connection
    parser.add_argument(
        "--cloud-url",
        type=str,
        default=os.getenv("QDRANT_CLOUD_URL"),
        help="Qdrant cloud URL (default: from QDRANT_CLOUD_URL env var)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("QDRANT_CLOUD_API_KEY"),
        help="Qdrant API key (default: from QDRANT_CLOUD_API_KEY env var)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="legislation_section",
        choices=["legislation", "legislation_section"],
        help="Qdrant collection to search (default: legislation_section)",
    )

    # Search parameters
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of results to retrieve (default: 100)",
    )
    parser.add_argument(
        "--year-from",
        type=int,
        help="Filter results from this year onwards (e.g., 2010)",
    )
    parser.add_argument(
        "--year-to",
        type=int,
        help="Filter results up to this year (e.g., 2024)",
    )
    parser.add_argument(
        "--types",
        type=str,
        nargs="+",
        help="Filter by legislation types (e.g., ukpga uksi wsi)",
    )

    # Output options
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for exports (default: ./lex_exports_TIMESTAMP)",
    )
    parser.add_argument(
        "--formats",
        type=str,
        nargs="+",
        default=["csv", "excel", "json"],
        choices=["csv", "excel", "json"],
        help="Export formats (default: csv excel json)",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Skip displaying results table",
    )

    args = parser.parse_args()

    # Print header
    console.print("\n[bold cyan]LEX - UK Legislation Semantic Search Tool[/bold cyan]")
    console.print("=" * 70)

    # Check Azure OpenAI credentials
    if not os.getenv("AZURE_OPENAI_API_KEY"):
        console.print("[red]✗[/red] AZURE_OPENAI_API_KEY not set")
        console.print("[yellow]Set environment variables for Azure OpenAI:[/yellow]")
        console.print("  export AZURE_OPENAI_API_KEY=your_key")
        console.print("  export AZURE_OPENAI_ENDPOINT=your_endpoint")
        console.print("  export AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large")
        return

    # Check Qdrant credentials
    if not args.cloud_url or not args.api_key:
        console.print("[red]✗[/red] Qdrant credentials not set")
        console.print("[yellow]Set environment variables:[/yellow]")
        console.print("  export QDRANT_CLOUD_URL=your_url")
        console.print("  export QDRANT_CLOUD_API_KEY=your_key")
        console.print("[yellow]Or pass as arguments:[/yellow]")
        console.print("  --cloud-url YOUR_URL --api-key YOUR_KEY")
        return

    # Create Qdrant client
    try:
        client = create_qdrant_client(args.cloud_url, args.api_key)
        console.print("[green]✓[/green] Connected to Qdrant")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to connect to Qdrant: {e}")
        return

    # Build filters
    filters = build_filters(args.year_from, args.year_to, args.types)

    # Perform semantic search
    try:
        results = semantic_search(
            client=client,
            collection_name=args.collection,
            query=args.query,
            limit=args.limit,
            filters=filters,
        )
    except Exception as e:
        console.print(f"[red]✗[/red] Search failed: {e}")
        import traceback

        traceback.print_exc()
        return

    # Display preview table
    if results and not args.no_preview:
        display_results_table(results)

    # Export results
    try:
        export_results(
            results=results,
            query=args.query,
            formats=args.formats,
            output_dir=args.output,
        )
    except Exception as e:
        console.print(f"[red]✗[/red] Export failed: {e}")
        return

    console.print("\n[bold green]✓ Complete![/bold green]")
    console.print(f"[dim]Query: {args.query}[/dim]")
    console.print(f"[dim]Results: {len(results)}[/dim]")


if __name__ == "__main__":
    main()
