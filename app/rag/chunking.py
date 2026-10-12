def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    if max_chars <= 0 or overlap < 0 or overlap >= max_chars:
        raise ValueError("Require max_chars > overlap >= 0")
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks, start = [], 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start + max_chars // 2, end)
            if boundary > start:
                end = boundary
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = end - overlap
    return chunks
