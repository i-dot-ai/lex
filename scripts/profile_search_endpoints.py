"""Profile search endpoint performance with varied queries."""

import asyncio
import sys
import time
from pathlib import Path
from statistics import mean, median, stdev

import httpx
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))

from _console import console, print_header, print_summary

API_URL = "http://localhost:8000"

# 10 diverse queries covering different complexity levels (novel terms to avoid cache)
TEST_QUERIES = [
    "maritime salvage rights",  # Specialized area
    "compulsory purchase compensation",  # Administrative law
    "defamation libel damages",  # Tort law
    "intellectual property patent infringement",  # IP law
    "consumer protection unfair terms",  # Consumer law
    "environmental pollution liability",  # Environmental law
    "insolvency bankruptcy procedure",  # Insolvency law
    "immigration asylum refugee status",  # Immigration law
    "landlord tenant eviction notice",  # Property law
    "corporate directors fiduciary duty",  # Corporate law
]


async def time_request(client: httpx.AsyncClient, url: str, payload: dict) -> float:
    """Make request and return response time in seconds."""
    start = time.perf_counter()
    try:
        response = await client.post(url, json=payload, timeout=60.0)
        response.raise_for_status()
        elapsed = time.perf_counter() - start
        return elapsed
    except Exception as e:
        console.print(f"  [red]Error: {e}[/red]")
        return -1.0


async def profile_endpoint(endpoint: str, endpoint_name: str, payload_builder) -> dict:
    """Profile a single endpoint with all test queries."""
    console.print(f"\n[bold]Profiling: {endpoint_name}[/bold]")
    console.rule()

    times = []

    async with httpx.AsyncClient() as client:
        for i, query in enumerate(TEST_QUERIES, 1):
            payload = payload_builder(query)
            console.print(f"\n{i}. Query: '{query}'")

            elapsed = await time_request(client, f"{API_URL}{endpoint}", payload)

            if elapsed > 0:
                times.append(elapsed)
                console.print(f"   [green]{elapsed:.3f}s[/green]")
            else:
                console.print("   [red]Failed[/red]")

    if not times:
        return {"endpoint": endpoint_name, "error": "All requests failed"}

    return {
        "endpoint": endpoint_name,
        "queries_tested": len(TEST_QUERIES),
        "successful": len(times),
        "failed": len(TEST_QUERIES) - len(times),
        "mean": mean(times),
        "median": median(times),
        "min": min(times),
        "max": max(times),
        "stdev": stdev(times) if len(times) > 1 else 0,
        "all_times": times,
    }


async def main():
    """Run profiling on all endpoints."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark search endpoint response times (requires local API on port 8000)",
    )
    parser.parse_args()

    print_header(
        "Search Endpoint Profiler",
        details={
            "Queries per endpoint": str(len(TEST_QUERIES)),
            "API": API_URL,
        },
    )

    # Profile legislation sections search
    sections_result = await profile_endpoint(
        "/legislation/section/search",
        "Legislation Sections Search",
        lambda q: {"query": q, "size": 10},
    )

    # Profile legislation acts search
    acts_result = await profile_endpoint(
        "/legislation/search",
        "Legislation Acts Search",
        lambda q: {"query": q, "limit": 10, "use_semantic_search": True},
    )

    # Profile caselaw search
    caselaw_result = await profile_endpoint(
        "/caselaw/search",
        "Caselaw Search",
        lambda q: {"query": q, "size": 10, "is_semantic_search": True},
    )

    # Summary report
    results = [sections_result, acts_result, caselaw_result]

    table = Table(title="Performance Summary", border_style="blue", expand=False)
    table.add_column("Endpoint", style="bold")
    table.add_column("OK", justify="right")
    table.add_column("Mean", justify="right")
    table.add_column("Median", justify="right")
    table.add_column("Min", justify="right")
    table.add_column("Max", justify="right")
    table.add_column("StdDev", justify="right")

    for result in results:
        if "error" in result:
            table.add_row(
                result["endpoint"],
                "[red]FAILED[/red]",
                "-",
                "-",
                "-",
                "-",
                "-",
            )
            continue
        table.add_row(
            result["endpoint"],
            f"{result['successful']}/{result['queries_tested']}",
            f"{result['mean']:.3f}s",
            f"{result['median']:.3f}s",
            f"{result['min']:.3f}s",
            f"{result['max']:.3f}s",
            f"{result['stdev']:.3f}s",
        )

    console.print()
    console.print(table)

    # Ranking
    valid_results = [r for r in results if "error" not in r]
    ranked = sorted(valid_results, key=lambda x: x["median"])

    ranking_stats = {}
    for i, result in enumerate(ranked, 1):
        ranking_stats[f"{i}. {result['endpoint']}"] = f"{result['median']:.3f}s median"

    print_summary(
        "Ranking (by median response time)",
        ranking_stats,
        success=len(valid_results) > 0,
    )


if __name__ == "__main__":
    asyncio.run(main())
