#!/usr/bin/env python
"""
Performance test for legislation search endpoint.
Tests the same query and measures response time.
"""
import asyncio
import time
from backend.legislation.models import LegislationActSearch
from backend.legislation.search import legislation_act_search


async def test_search_performance():
    """Test search performance with timing."""

    # Test query from user report
    search_request = LegislationActSearch(
        query="Chagos islands",
        year_to=2025,
        legislation_type=["ukpga", "uksi"],
        use_semantic_search=True,
        offset=0,
        limit=20
    )

    print("Testing legislation search performance...")
    print(f"Query: {search_request.query}")
    print(f"Types: {search_request.legislation_type}")
    print(f"Page size: {search_request.limit}")
    print("-" * 60)

    start = time.time()
    result = await legislation_act_search(search_request)
    elapsed = time.time() - start

    print(f"\n✓ Search completed in {elapsed:.3f}s")
    print(f"  - Results: {len(result['results'])}")
    print(f"  - Total: {result['total']}")
    print(f"  - Response size: ~{len(str(result)) // 1024}KB")
    print("\nCheck backend logs for detailed timing breakdown.")


if __name__ == "__main__":
    asyncio.run(test_search_performance())
