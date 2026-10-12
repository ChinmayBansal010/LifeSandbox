from dataclasses import dataclass

from app.rag.embeddings import cosine, embed


@dataclass(frozen=True)
class Passage:
    owner_id: str
    source_id: str
    text: str
    vector: list[float]


def retrieve(
    query: str, owner_id: str, passages: list[Passage], limit: int = 5, threshold: float = 0.05
) -> list[tuple[Passage, float]]:
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    query_vector = embed(query)
    ranked = [(p, cosine(query_vector, p.vector)) for p in passages if p.owner_id == owner_id]
    return sorted(
        (item for item in ranked if item[1] >= threshold), key=lambda item: item[1], reverse=True
    )[:limit]
