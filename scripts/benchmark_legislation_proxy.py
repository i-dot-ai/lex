#!/usr/bin/env python3
"""Benchmark legislation proxy performance vs direct access."""

import asyncio
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)


async def benchmark_direct(legislation_path: str) -> dict:
    """Benchmark direct access to legislation.gov.uk."""
    url = f"https://www.legislation.gov.uk/{legislation_path}"

    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        content = response.text
    end = time.time()

    return {
        "url": url,
        "duration": end - start,
        "size_kb": len(content) / 1024,
        "status": response.status_code,
    }


async def benchmark_proxy(legislation_path: str, backend_url: str = "http://localhost:8000") -> dict:
    """Benchmark access through our FastAPI proxy."""
    url = f"{backend_url}/legislation/proxy/{legislation_path}"

    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        content = response.text
    end = time.time()

    return {
        "url": url,
        "duration": end - start,
        "size_kb": len(content) / 1024,
        "status": response.status_code,
    }


async def main():
    """Run benchmarks on various legislation types."""

    # Test cases: mix of different types and sizes
    test_cases = [
        ("ukpga/2018/12/data.html", "Data Protection Act 2018 (large)"),
        ("ukpga/2024/9/data.html", "Arbitration Act 2024 (medium)"),
        ("ukpga/1998/42/data.html", "Human Rights Act 1998 (medium)"),
        ("uksi/2024/1/data.html", "UKSI 2024/1 (small SI)"),
        ("uksi/2005/314/data.html", "UKSI 2005/314 (medium SI)"),
        ("ukpga/2020/1/data.html", "European Union Act 2020 (small)"),
    ]

    print("=" * 80)
    print("LEGISLATION PROXY PERFORMANCE BENCHMARK")
    print("=" * 80)
    print()

    results = []

    for path, description in test_cases:
        print(f"\n📄 {description}")
        print(f"   Path: {path}")
        print("-" * 80)

        # Benchmark direct access
        try:
            direct_result = await benchmark_direct(path)
            print(f"   ✅ DIRECT:  {direct_result['duration']:.3f}s ({direct_result['size_kb']:.1f} KB)")
        except Exception as e:
            print(f"   ❌ DIRECT:  Failed - {e}")
            direct_result = {"duration": None, "size_kb": None, "error": str(e)}

        # Small delay between requests
        await asyncio.sleep(0.5)

        # Benchmark proxy access
        try:
            proxy_result = await benchmark_proxy(path)
            print(f"   🔄 PROXY:   {proxy_result['duration']:.3f}s ({proxy_result['size_kb']:.1f} KB)")
        except Exception as e:
            print(f"   ❌ PROXY:   Failed - {e}")
            proxy_result = {"duration": None, "size_kb": None, "error": str(e)}

        # Calculate overhead
        if direct_result['duration'] and proxy_result['duration']:
            overhead = proxy_result['duration'] - direct_result['duration']
            overhead_pct = (overhead / direct_result['duration']) * 100
            print(f"   📊 OVERHEAD: +{overhead:.3f}s ({overhead_pct:+.1f}%)")

        results.append({
            "path": path,
            "description": description,
            "direct": direct_result,
            "proxy": proxy_result,
        })

        # Cool down between tests
        await asyncio.sleep(1)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    valid_results = [r for r in results if r['direct']['duration'] and r['proxy']['duration']]

    if valid_results:
        avg_direct = sum(r['direct']['duration'] for r in valid_results) / len(valid_results)
        avg_proxy = sum(r['proxy']['duration'] for r in valid_results) / len(valid_results)
        avg_overhead = avg_proxy - avg_direct
        avg_overhead_pct = (avg_overhead / avg_direct) * 100

        print(f"\nAverage Direct:   {avg_direct:.3f}s")
        print(f"Average Proxy:    {avg_proxy:.3f}s")
        print(f"Average Overhead: +{avg_overhead:.3f}s ({avg_overhead_pct:+.1f}%)")

        # Find slowest
        slowest = max(valid_results, key=lambda r: r['proxy']['duration'])
        print(f"\nSlowest (proxy):  {slowest['description']} - {slowest['proxy']['duration']:.3f}s ({slowest['proxy']['size_kb']:.1f} KB)")

        # Find largest
        largest = max(valid_results, key=lambda r: r['proxy']['size_kb'])
        print(f"Largest:          {largest['description']} - {largest['proxy']['size_kb']:.1f} KB")


if __name__ == "__main__":
    asyncio.run(main())
