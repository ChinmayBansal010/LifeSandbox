"""Test suite for RAG & Cross-Conversation Memory Evaluation Harness.

Validates information retrieval benchmarks (Hit@K, MRR, NDCG), groundedness scoring,
chunking integrity, and tenant isolation guarantees.
"""

from __future__ import annotations

import pytest

from app.rag.chunking import chunk_text
from evals.rag_harness import (
    RAGHarness,
    RAGMetricsEvaluator,
    SyntheticCorpusFactory,
    TenantIsolationAuditor,
)


def test_rag_metrics_evaluator_reciprocal_rank():
    # Rank 1 -> 1.0
    assert RAGMetricsEvaluator.reciprocal_rank(["doc_a", "doc_b", "doc_c"], "doc_a") == 1.0
    # Rank 2 -> 0.5
    assert RAGMetricsEvaluator.reciprocal_rank(["doc_a", "doc_b", "doc_c"], "doc_b") == 0.5
    # Rank 3 -> 1/3
    assert pytest.approx(RAGMetricsEvaluator.reciprocal_rank(["doc_a", "doc_b", "doc_c"], "doc_c"), 0.001) == 0.3333
    # Not found -> 0.0
    assert RAGMetricsEvaluator.reciprocal_rank(["doc_a", "doc_b"], "doc_x") == 0.0


def test_rag_metrics_evaluator_ndcg_at_k():
    # Perfect top 1 ranking
    assert RAGMetricsEvaluator.ndcg_at_k(["target", "other1", "other2"], "target", k=3) == 1.0
    # Rank 2 position has discounted gain
    ndcg_rank2 = RAGMetricsEvaluator.ndcg_at_k(["other1", "target", "other2"], "target", k=3)
    assert 0.0 < ndcg_rank2 < 1.0
    # Outside top k gives 0
    assert RAGMetricsEvaluator.ndcg_at_k(["other1", "other2"], "target", k=2) == 0.0


def test_rag_groundedness_evaluator_faithful_vs_hallucinated():
    context = (
        "LifeSandbox is an autonomous AI agent simulator designed to evaluate life trade-offs, "
        "personal finance trajectories, career pivot decisions, and calendar scheduling."
    )
    faithful = "LifeSandbox evaluates personal finance trajectories and calendar scheduling."
    score_faithful = RAGMetricsEvaluator.evaluate_groundedness(faithful, context)
    assert score_faithful.is_faithful is True
    assert score_faithful.groundedness_ratio >= 0.8
    assert len(score_faithful.hallucinated_tokens) == 0

    hallucinated = "LifeSandbox launches supersonic passenger rockets into Mars orbit."
    score_hallucinated = RAGMetricsEvaluator.evaluate_groundedness(hallucinated, context)
    assert score_hallucinated.is_faithful is False
    assert score_hallucinated.groundedness_ratio < 0.5
    assert any("rocket" in t or "orbit" in t or "mars" in t for t in score_hallucinated.hallucinated_tokens)


def test_tenant_isolation_auditor_detects_cross_user_leak():
    corpus_alice = SyntheticCorpusFactory.create_corpus("user_alice")
    corpus_bob = SyntheticCorpusFactory.create_corpus("user_bob")

    # Clean retrieval with only Alice's passages
    clean_audit = TenantIsolationAuditor.audit_retrieval("user_alice", corpus_alice)
    assert clean_audit.passed is True
    assert clean_audit.cross_tenant_leaks == 0

    # Contaminated retrieval containing Bob's passage
    leaked_audit = TenantIsolationAuditor.audit_retrieval("user_alice", [corpus_alice[0], corpus_bob[0]])
    assert leaked_audit.passed is False
    assert leaked_audit.cross_tenant_leaks == 1


def test_rag_harness_end_to_end_benchmarks():
    harness = RAGHarness()
    results = harness.run_all()

    assert results["overall_passed"] is True
    assert results["retrieval_benchmark"]["hit_rate_at_3"] >= 0.8
    assert results["retrieval_benchmark"]["mean_reciprocal_rank"] >= 0.7
    assert results["isolation_audit"]["passed"] is True
    assert results["groundedness_checks"]["passed"] is True


def test_rag_chunking_boundaries_and_overlap():
    markdown = (
        "# Section 1: Overview\n"
        "Here is the core premise of LifeSandbox.\n\n"
        "## Section 2: Details\n"
        "Detailed financial analysis with compound growth models.\n\n"
        "### Section 3: Caveats\n"
        "Always account for inflation and volatility."
    )
    chunks = chunk_text(markdown, max_chars=80, overlap=10)
    assert len(chunks) >= 2
    # Ensure headings are retained in chunk headers or text
    assert any("Overview" in c for c in chunks)
    assert any("Caveats" in c for c in chunks)
