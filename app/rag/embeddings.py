"""Deterministic development embeddings; replace with a model-backed provider for production."""

import hashlib
import math


def embed(text: str, dimensions: int = 128) -> list[float]:
    vector = [0.0] * dimensions
    for token in text.lower().split():
        raw = hashlib.blake2b(token.encode(), digest_size=16).digest()
        idx = int.from_bytes(raw[:4], "big") % dimensions
        vector[idx] += 1.0 if raw[4] & 1 else -1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Embedding dimensions must match")
    return sum(x * y for x, y in zip(a, b, strict=True))
