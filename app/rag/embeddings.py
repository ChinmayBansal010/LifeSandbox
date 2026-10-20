"""Model-backed and deterministic embeddings for RAG and semantic retrieval."""

import hashlib
import logging
import math

from app.core.config import get_settings

logger = logging.getLogger("life_sandbox.rag.embeddings")

_fastembed_model_instance = None


def _get_fastembed_model(model_name: str):
    global _fastembed_model_instance
    if _fastembed_model_instance is None:
        from fastembed import TextEmbedding

        _fastembed_model_instance = TextEmbedding(model_name=model_name)
    return _fastembed_model_instance


def _local_hash_embed(text: str, dimensions: int = 128) -> list[float]:
    vector = [0.0] * dimensions
    for token in text.lower().split():
        raw = hashlib.blake2b(token.encode(), digest_size=16).digest()
        idx = int.from_bytes(raw[:4], "big") % dimensions
        vector[idx] += 1.0 if raw[4] & 1 else -1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [float(x / norm) for x in vector]


def _openai_embed(texts: list[str], model: str) -> list[list[float]]:
    settings = get_settings()
    api_key = (
        settings.openai_api_key
        or settings.nebius_api_key
        or settings.openrouter_api_key
    )
    if not api_key:
        raise ValueError("OpenAI embedding requires configured API key")
    base_url = None
    if not settings.openai_api_key and settings.nebius_api_key:
        base_url = settings.nebius_base_url
    elif not settings.openai_api_key and settings.openrouter_api_key:
        base_url = settings.openrouter_base_url

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    res = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in res.data]


def embed_many(texts: list[str], dimensions: int | None = None) -> list[list[float]]:
    """Embed multiple texts in batch using the configured embedding provider."""
    if not texts:
        return []

    settings = get_settings()
    provider = settings.embedding_provider

    if provider == "openai":
        try:
            return _openai_embed(texts, settings.openai_embedding_model)
        except Exception as exc:
            logger.warning("OpenAI embedding failed, falling back to FastEmbed/local: %s", exc)
            provider = "fastembed"

    if provider == "fastembed":
        try:
            model = _get_fastembed_model(settings.fastembed_model)
            embeddings = [vec.tolist() for vec in model.embed(texts)]
            return embeddings
        except Exception as exc:
            logger.warning("FastEmbed failed, falling back to local hash: %s", exc)
            provider = "local_hash"

    dims = dimensions or settings.embedding_dimensions or 128
    return [_local_hash_embed(t, dims) for t in texts]


def embed(text: str, dimensions: int | None = None) -> list[float]:
    """Embed a single text string."""
    results = embed_many([text], dimensions=dimensions)
    return results[0] if results else []


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Embedding dimensions must match")
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return float(dot / (norm_a * norm_b))
