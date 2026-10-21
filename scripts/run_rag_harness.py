#!/usr/bin/env python3
"""CLI runner for RAG and Cross-Conversation Retrieval Evaluation Harness.

Usage:
    python scripts/run_rag_harness.py --suite all --output evals/reports/rag_eval.json
    python scripts/run_rag_harness.py --suite retrieval --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.rag_harness import RAGHarness  # noqa: E402


def run_rag_harness(suite: str = "all", verbose: bool = False) -> dict:
    harness = RAGHarness()
    print("=" * 65)
    print("      LifeSandbox RAG & Retrieval Benchmark Harness      ")
    print("=" * 65)

    report: dict = {}
    if suite in ("retrieval", "all"):
        print("\n[RAG Harness] Running IR Retrieval Benchmarks (Hit@K, MRR, NDCG)...")
        retrieval_res = harness.run_retrieval_benchmark()
        report["retrieval_benchmark"] = retrieval_res.__dict__
        print(f"  Hit Rate@1: {retrieval_res.hit_rate_at_1 * 100:.1f}%")
        print(f"  Hit Rate@3: {retrieval_res.hit_rate_at_3 * 100:.1f}%")
        print(f"  Hit Rate@5: {retrieval_res.hit_rate_at_5 * 100:.1f}%")
        print(f"  Mean Reciprocal Rank (MRR): {retrieval_res.mean_reciprocal_rank:.4f}")
        print(f"  NDCG@5: {retrieval_res.mean_ndcg_at_5:.4f}")
        print(f"  Passed Gate: {retrieval_res.passed} (took {retrieval_res.duration_ms:.2f}ms)")

    if suite in ("isolation", "all"):
        print("\n[RAG Harness] Running Multi-Tenant Isolation Audit...")
        isolation_res = harness.run_isolation_audit()
        report["isolation_audit"] = isolation_res.__dict__
        print(f"  Cross-Tenant Leaks Detected: {isolation_res.cross_tenant_leaks}")
        print(f"  Passed Isolation Gate: {isolation_res.passed}")

    if suite in ("groundedness", "all"):
        print("\n[RAG Harness] Running Context Groundedness & Faithfulness Scoring...")
        res = harness.run_all()
        report["groundedness_checks"] = res["groundedness_checks"]
        g_pass = res["groundedness_checks"]["passed"]
        print(f"  Groundedness & Anti-Hallucination Verification: {'PASSED' if g_pass else 'FAILED'}")

    report["overall_passed"] = all(
        v.get("passed", True) for v in report.values() if isinstance(v, dict) and "passed" in v
    )
    return report


def main():
    parser = argparse.ArgumentParser(description="Execute RAG & Retrieval evaluation harness.")
    parser.add_argument(
        "--suite",
        choices=["all", "retrieval", "isolation", "groundedness"],
        default="all",
        help="Evaluation suite to execute",
    )
    parser.add_argument("--output", type=str, default=None, help="Path to write JSON benchmark report")
    parser.add_argument("--verbose", action="store_true", help="Print verbose metrics")
    args = parser.parse_args()

    results = run_rag_harness(suite=args.suite, verbose=args.verbose)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\n[RAG Harness] Benchmark report written to: {out_path}")

    overall_passed = results.get("overall_passed", True)
    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
