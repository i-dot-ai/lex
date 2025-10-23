"""Profile search endpoint performance with varied queries."""

import asyncio
import time
from statistics import mean, median, stdev
import httpx

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
        print(f"  ❌ Error: {e}")
        return -1.0


async def profile_endpoint(endpoint: str, endpoint_name: str, payload_builder) -> dict:
    """Profile a single endpoint with all test queries."""
    print(f"\n{'=' * 60}")
    print(f"🔍 Profiling: {endpoint_name}")
    print(f"{'=' * 60}")

    times = []

    async with httpx.AsyncClient() as client:
        for i, query in enumerate(TEST_QUERIES, 1):
            payload = payload_builder(query)
            print(f"\n{i}. Query: '{query}'")

            elapsed = await time_request(client, f"{API_URL}{endpoint}", payload)

            if elapsed > 0:
                times.append(elapsed)
                print(f"   ✓ {elapsed:.3f}s")
            else:
                print(f"   ✗ Failed")

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
    print("\n" + "=" * 60)
    print("🚀 Search Endpoint Performance Profiling")
    print("=" * 60)
    print(f"Testing {len(TEST_QUERIES)} queries per endpoint")
    print(f"API: {API_URL}")

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
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 60)

    results = [sections_result, acts_result, caselaw_result]

    for result in results:
        if "error" in result:
            print(f"\n❌ {result['endpoint']}: {result['error']}")
            continue

        print(f"\n{result['endpoint']}")
        print(f"  Successful: {result['successful']}/{result['queries_tested']}")
        print(f"  Mean:   {result['mean']:.3f}s")
        print(f"  Median: {result['median']:.3f}s")
        print(f"  Min:    {result['min']:.3f}s")
        print(f"  Max:    {result['max']:.3f}s")
        print(f"  StdDev: {result['stdev']:.3f}s")

    # Ranking
    print("\n" + "=" * 60)
    print("🏆 RANKING (by median response time)")
    print("=" * 60)

    valid_results = [r for r in results if "error" not in r]
    ranked = sorted(valid_results, key=lambda x: x["median"])

    for i, result in enumerate(ranked, 1):
        print(f"{i}. {result['endpoint']}: {result['median']:.3f}s median")

    print("\n✅ Profiling complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
