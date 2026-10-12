import pytest

from app.rag.chunking import chunk_text
from app.rag.embeddings import cosine, embed
from app.rag.retrieval import Passage, retrieve


def test_chunking_has_overlap_and_rejects_bad_configuration():
    chunks = chunk_text("alpha " * 100, max_chars=50, overlap=10)
    assert len(chunks) > 1
    assert chunks[0][-10:] == chunks[1][:10]
    with pytest.raises(ValueError):
        chunk_text("x", max_chars=10, overlap=10)


def test_hash_embeddings_are_stable_and_tenant_filtered():
    assert embed("same input") == embed("same input")
    assert cosine(embed("decision plan"), embed("decision plan")) == pytest.approx(1.0)
    rows = [
        Passage("a", "1", "private passage", embed("private passage")),
        Passage("b", "2", "other", embed("private passage")),
    ]
    assert [p.owner_id for p, _ in retrieve("private passage", "a", rows)] == ["a"]
