"""Dense vector, sparse lexical, and hybrid search retrieval with Reciprocal Rank Fusion (RRF)."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import FileChunkRow, FileRow
from app.rag.embeddings import cosine, embed


@dataclass(frozen=True)
class Passage:
    owner_id: str
    source_id: str
    text: str
    vector: list[float]


@dataclass
class DocumentChunkResult:
    chunk_id: str
    file_id: str
    filename: str
    page_number: int | None
    content: str
    score: float


def reciprocal_rank_fusion(
    ranked_lists: list[list[Any]],
    k: int = 60,
    key_fn: Callable[[Any], Any] | None = None,
) -> list[tuple[Any, float]]:
    """Combine multiple ranked lists into a single ranked list using Reciprocal Rank Fusion."""
    scores: dict[Any, float] = {}
    item_map: dict[Any, Any] = {}

    for r_list in ranked_lists:
        for rank, item in enumerate(r_list, start=1):
            key = key_fn(item) if key_fn else item
            scores[key] = scores.get(key, 0.0) + (1.0 / (k + rank))
            if key not in item_map:
                item_map[key] = item

    sorted_keys = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return [(item_map[key], score) for key, score in sorted_keys]


def _text_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", text.lower()))


async def search_user_documents(
    db: AsyncSession,
    user_id: str,
    query: str,
    limit: int = 5,
    file_ids: list[str] | None = None,
) -> list[DocumentChunkResult]:
    """Perform hybrid retrieval over document chunks using vector and text search with RRF."""
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")

    file_filter = [FileRow.user_id == user_id, FileRow.status == "ready"]
    if file_ids:
        file_filter.append(FileRow.id.in_(file_ids))

    files = list((await db.scalars(select(FileRow).where(*file_filter))).all())
    if not files:
        return []

    valid_file_ids = [f.id for f in files]
    file_lookup = {f.id: f.filename for f in files}

    chunk_filter = [
        FileChunkRow.user_id == user_id,
        FileChunkRow.file_id.in_(valid_file_ids),
    ]

    all_chunks = list((await db.scalars(select(FileChunkRow).where(*chunk_filter))).all())
    if not all_chunks:
        return []

    query_vec = embed(query)
    dialect_name = getattr(db.bind, "dialect", None)
    dialect = getattr(dialect_name, "name", "") if dialect_name else ""

    # 1. Dense vector ranking
    dense_ranked_chunks: list[FileChunkRow] = []
    if dialect == "postgresql":
        try:
            vector_stmt = (
                select(FileChunkRow)
                .where(*chunk_filter, FileChunkRow.embedding.is_not(None))
                .order_by(FileChunkRow.embedding.cosine_distance(query_vec))
                .limit(limit * 3)
            )
            dense_ranked_chunks = list((await db.scalars(vector_stmt)).all())
        except Exception:
            dense_ranked_chunks = []

    if not dense_ranked_chunks:
        # Fallback scoring in memory
        scored_dense: list[tuple[FileChunkRow, float]] = []
        for ch in all_chunks:
            vec = ch.embedding if ch.embedding is not None else embed(ch.content)
            try:
                sc = cosine(query_vec, vec)
                scored_dense.append((ch, sc))
            except Exception:
                continue
        scored_dense.sort(key=lambda p: p[1], reverse=True)
        dense_ranked_chunks = [p[0] for p in scored_dense[: limit * 3]]

    # 2. Sparse text / lexical ranking
    query_terms = _text_tokens(query)
    scored_sparse: list[tuple[FileChunkRow, float]] = []
    for ch in all_chunks:
        ch_terms = _text_tokens(ch.content)
        overlap = len(query_terms & ch_terms)
        if overlap > 0:
            scored_sparse.append((ch, float(overlap) / max(len(query_terms), 1)))

    scored_sparse.sort(key=lambda p: p[1], reverse=True)
    sparse_ranked_chunks = [p[0] for p in scored_sparse[: limit * 3]]

    # 3. Fuse with Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion(
        [dense_ranked_chunks, sparse_ranked_chunks],
        k=60,
        key_fn=lambda ch: ch.id,
    )

    results: list[DocumentChunkResult] = []
    for chunk, score in fused[:limit]:
        filename = file_lookup.get(chunk.file_id, "unknown")
        results.append(
            DocumentChunkResult(
                chunk_id=chunk.id,
                file_id=chunk.file_id,
                filename=filename,
                page_number=chunk.page_number,
                content=chunk.content,
                score=score,
            )
        )
    return results


def retrieve(
    query: str,
    owner_id: str,
    passages: list[Passage],
    limit: int = 5,
    threshold: float = 0.05,
) -> list[tuple[Passage, float]]:
    """Legacy passage retrieval with dense cosine similarity."""
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    query_vector = embed(query)
    ranked = [(p, cosine(query_vector, p.vector)) for p in passages if p.owner_id == owner_id]
    return sorted(
        (item for item in ranked if item[1] >= threshold),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]
