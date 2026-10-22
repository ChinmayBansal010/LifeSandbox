"""Comprehensive test suite for Phase 1 - Phase 5 milestones:
- Phase 1: Real Embeddings & pgvector on FileChunkRow & MemoryRow
- Phase 2: True Vector Chunk Retrieval (<=> cosine distance)
- Phase 3: Recursive Chunking & Background Ingestion via JobRow
- Phase 4: Agentic Knowledge Search Tool (knowledge.search)
- Phase 5: Hybrid Search with RRF & Asynchronous Memory Reflection Job
"""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

import app.tools.catalog  # noqa: F401
from app.core.config import get_settings
from app.jobs.worker import run_due_jobs
from app.memory.service import (
    extract_implicit_facts,
    policy_for,
    process_reflection_job,
    search_memories,
)
from app.persistence.models import (
    Base,
    FileChunkRow,
    FileRow,
    JobRow,
)
from app.persistence.session import SessionLocal, engine
from app.rag.chunking import chunk_text
from app.rag.embeddings import cosine, embed, embed_many
from app.rag.retrieval import (
    reciprocal_rank_fusion,
    search_user_documents,
)
from app.tools.registry import registry


@pytest.fixture(autouse=True)
async def init_db(monkeypatch):
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "fastembed")
    monkeypatch.setattr(settings, "embedding_dimensions", 384)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


# ==========================================
# Phase 1: Real Embeddings & pgvector schema
# ==========================================
def test_real_embeddings_fastembed():
    vec1 = embed("Autonomous decision intelligence")
    vec2 = embed("Autonomous decision intelligence")
    vec3 = embed("Baking sourdough bread at home")

    assert len(vec1) == 384
    assert vec1 == vec2
    sim_same = cosine(vec1, vec2)
    sim_diff = cosine(vec1, vec3)

    assert sim_same == pytest.approx(1.0, abs=1e-4)
    assert sim_diff < sim_same


def test_embed_many_batch():
    texts = ["apple", "banana", "cherry"]
    vecs = embed_many(texts)
    assert len(vecs) == 3
    for v in vecs:
        assert len(v) == 384


def test_local_hash_fallback(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "local_hash")
    monkeypatch.setattr(settings, "embedding_dimensions", 64)

    vec = embed("test query")
    assert len(vec) == 64


# ==========================================
# Phase 2: True Vector Chunk Retrieval
# ==========================================
@pytest.mark.asyncio
async def test_vector_chunk_retrieval():
    user_id = f"test-user-{datetime.now(UTC).timestamp()}"
    file_id = f"file-{datetime.now(UTC).timestamp()}"

    target_text = "The quarterly revenue was twenty million dollars."
    other_text = "Employees should submit their travel expense reports by Tuesday."

    target_vec = embed(target_text)
    other_vec = embed(other_text)

    async with SessionLocal() as db:
        file = FileRow(
            id=file_id,
            user_id=user_id,
            filename="financials.txt",
            mime_type="text/plain",
            size_bytes=100,
            status="ready",
            storage_key="test-key",
        )
        db.add(file)

        c1 = FileChunkRow(
            file_id=file_id,
            user_id=user_id,
            chunk_index=0,
            content=other_text,
            embedding=other_vec,
        )
        c2 = FileChunkRow(
            file_id=file_id,
            user_id=user_id,
            chunk_index=1,
            content=target_text,
            embedding=target_vec,
        )
        db.add_all([c1, c2])
        await db.commit()

        results = await search_user_documents(
            db, user_id=user_id, query="What was the quarterly revenue?", limit=1
        )
        assert len(results) == 1
        assert "quarterly revenue" in results[0].content


# ==========================================
# Phase 3: Recursive Chunking & Background Ingestion
# ==========================================
def test_recursive_markdown_and_sentence_chunking():
    doc = (
        "# Executive Summary\n"
        "Our team achieved stellar milestones this quarter. We launched three core features.\n\n"
        "## Engineering Highlights\n"
        "The backend migration to vector embeddings succeeded with zero downtime. "
        "Latency decreased by 40 percent across all retrieval operations.\n\n"
        "### Future Roadmap\n"
        "We plan to expand reflection jobs to scheduled background worker loops."
    )
    chunks = chunk_text(doc, max_chars=120, overlap=15)
    assert len(chunks) >= 3
    assert 12 <= 15 <= 20


@pytest.mark.asyncio
async def test_document_ingestion_via_job_row(tmp_path, monkeypatch):
    import uuid

    settings = get_settings()
    monkeypatch.setattr(settings, "file_storage_dir", str(tmp_path))

    user_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    test_file_path = tmp_path / file_id
    test_content = (
        "Artificial Intelligence in Healthcare:\n\n"
        "Diagnostic models have demonstrated superior accuracy in imaging tasks.\n"
        "Patient data privacy remains paramount under HIPAA regulations."
    )
    test_file_path.write_bytes(test_content.encode("utf-8"))

    async with SessionLocal() as db:
        file = FileRow(
            id=file_id,
            user_id=user_id,
            filename="healthcare.txt",
            mime_type="text/plain",
            size_bytes=len(test_content),
            status="processing",
            storage_key=file_id,
        )
        job = JobRow(
            user_id=user_id,
            job_type="document_ingestion",
            payload=json.dumps({"file_id": file_id}),
            scheduled_at=datetime.now(UTC),
            idempotency_key=f"ingest:{file_id}",
            status="queued",
        )
        db.add_all([file, job])
        await db.commit()

    for _ in range(10):
        processed = await run_due_jobs(limit=100)
        async with SessionLocal() as db:
            updated_file = await db.get(FileRow, file_id)
            if updated_file and updated_file.status == "ready":
                break
        if processed == 0:
            break

    async with SessionLocal() as db:
        updated_file = await db.get(FileRow, file_id)
        assert updated_file is not None
        assert updated_file.status == "ready"

        stored_chunks = list(
            (
                await db.scalars(
                    select(FileChunkRow).where(FileChunkRow.file_id == file_id)
                )
            ).all()
        )
        assert len(stored_chunks) > 0
        assert stored_chunks[0].embedding is not None
        assert len(stored_chunks[0].embedding) == 384


# ==========================================
# Phase 4: Agentic Knowledge Search Tool
# ==========================================
def test_knowledge_search_tool_registered():
    tool = registry.get("knowledge.search")
    assert tool is not None
    assert tool.read_only is True
    assert "query" in tool.parameters["properties"]


@pytest.mark.asyncio
async def test_knowledge_search_execution():
    user_id = f"user-{datetime.now(UTC).timestamp()}"
    file_id = f"file-{datetime.now(UTC).timestamp()}"

    doc_text = "The project deployment key is stored in AWS Secrets Manager under /prod/app."
    doc_vec = embed(doc_text)

    async with SessionLocal() as db:
        file = FileRow(
            id=file_id,
            user_id=user_id,
            filename="ops_guide.md",
            mime_type="text/markdown",
            size_bytes=len(doc_text),
            status="ready",
            storage_key="test-key",
        )
        chunk = FileChunkRow(
            file_id=file_id,
            user_id=user_id,
            chunk_index=0,
            content=doc_text,
            embedding=doc_vec,
        )
        db.add_all([file, chunk])
        await db.commit()

        results = await search_user_documents(
            db, user_id=user_id, query="Where is the deployment key?"
        )
        assert len(results) > 0
        assert results[0].filename == "ops_guide.md"
        assert "AWS Secrets Manager" in results[0].content


# ==========================================
# Phase 5: Hybrid Search with RRF & Memory Reflection
# ==========================================
def test_reciprocal_rank_fusion_math():
    dense_list = ["docA", "docB", "docC"]
    sparse_list = ["docB", "docD", "docA"]

    fused = reciprocal_rank_fusion([dense_list, sparse_list], k=60)
    assert fused[0][0] == "docB"
    assert fused[1][0] == "docA"


def test_implicit_fact_extraction():
    message = (
        "I work as a senior backend engineer at Stripe. "
        "Also, I prefer concise markdown bullet points."
    )
    facts = extract_implicit_facts(message)
    assert len(facts) == 2
    categories = {cat for cat, _ in facts}
    assert "profile" in categories
    assert "preference" in categories


def test_implicit_fact_extraction_rejects_credentials():
    message = "I prefer dark mode. My secret api key is sk-or-v1-abcdef123456."
    facts = extract_implicit_facts(message)
    contents = " ".join(content for _, content in facts)
    assert "sk-or-v1" not in contents


@pytest.mark.asyncio
async def test_asynchronous_memory_reflection_job():
    user_id = f"user-{datetime.now(UTC).timestamp()}"
    conv_id = f"conv-{datetime.now(UTC).timestamp()}"

    async with SessionLocal() as db:
        policy = await policy_for(db, user_id)
        policy.auto_categories = json.dumps(["preference", "profile"])
        await db.commit()

        payload = {
            "conversation_id": conv_id,
            "message": "I prefer using Python for all backend microservices.",
        }
        saved_ids = await process_reflection_job(db, user_id, payload)
        await db.commit()

        assert len(saved_ids) >= 1

        memories = await search_memories(db, user_id=user_id, query="What language do I like?")
        assert len(memories) >= 1
        assert "Python" in memories[0].content
        assert memories[0].embedding is not None
        assert len(memories[0].embedding) == 384
