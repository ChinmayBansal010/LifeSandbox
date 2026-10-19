#!/usr/bin/env python3
"""LifeSandbox Load & Concurrency Benchmark Harness.

Measures throughput, latency percentiles (p50, p95, p99), error rates,
and rate limiter behavior under concurrent loads.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from typing import Any

from app.core.rate_limit import SlidingWindowRateLimiter


async def run_rate_limiter_load_benchmark(
    concurrency: int, total_requests: int, limit: int, window_seconds: float
) -> dict[str, Any]:
    """Benchmark process-local rate limiter under high concurrent load."""
    limiter = SlidingWindowRateLimiter(limit=limit, window_seconds=window_seconds)
    latencies: list[float] = []
    allowed_count = 0
    blocked_count = 0

    semaphore = asyncio.Semaphore(concurrency)

    async def single_request(idx: int) -> None:
        nonlocal allowed_count, blocked_count
        client_key = f"client-{idx % 10}"  # 10 simulated clients
        async with semaphore:
            t0 = time.perf_counter()
            allowed = limiter.allow(client_key)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(latency_ms)
            if allowed:
                allowed_count += 1
            else:
                blocked_count += 1

    start_wall = time.perf_counter()
    tasks = [asyncio.create_task(single_request(i)) for i in range(total_requests)]
    await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_wall

    latencies.sort()
    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
    rps = total_requests / total_time if total_time > 0 else 0.0

    return {
        "benchmark": "rate_limiter_concurrent_burst",
        "concurrency": concurrency,
        "total_requests": total_requests,
        "total_time_seconds": round(total_time, 4),
        "requests_per_second": round(rps, 2),
        "allowed_requests": allowed_count,
        "blocked_requests": blocked_count,
        "latency_ms": {
            "min": round(min(latencies), 4) if latencies else 0.0,
            "max": round(max(latencies), 4) if latencies else 0.0,
            "mean": round(statistics.mean(latencies), 4) if latencies else 0.0,
            "p50": round(p50, 4),
            "p95": round(p95, 4),
            "p99": round(p99, 4),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LifeSandbox Load & Concurrency Harness")
    parser.add_argument("--concurrency", type=int, default=50, help="Concurrent workers")
    parser.add_argument("--requests", type=int, default=1000, help="Total requests to dispatch")
    parser.add_argument("--limit", type=int, default=100, help="Rate limit capacity")
    parser.add_argument("--window", type=float, default=1.0, help="Rate limit window in seconds")
    parser.add_argument("--output", type=str, default="", help="Path to write JSON report")
    args = parser.parse_args()

    print(
        f"Starting load benchmark: {args.requests} requests, "
        f"concurrency={args.concurrency}, limit={args.limit}..."
    )
    results = asyncio.run(
        run_rate_limiter_load_benchmark(
            concurrency=args.concurrency,
            total_requests=args.requests,
            limit=args.limit,
            window_seconds=args.window,
        )
    )

    print("\n=== LifeSandbox Load Benchmark Results ===")
    print(f"Total Requests:       {results['total_requests']}")
    print(f"Concurrency:          {results['concurrency']}")
    print(f"Elapsed Time:         {results['total_time_seconds']}s")
    print(f"Throughput:           {results['requests_per_second']} req/s")
    print(f"Allowed / Blocked:    {results['allowed_requests']} / {results['blocked_requests']}")
    print(f"Latency P50:          {results['latency_ms']['p50']} ms")
    print(f"Latency P95:          {results['latency_ms']['p95']} ms")
    print(f"Latency P99:          {results['latency_ms']['p99']} ms")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nReport saved to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
