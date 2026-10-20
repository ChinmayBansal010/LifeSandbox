"""Sentence and markdown-aware recursive chunking with bounded overlap."""

import re

SEPARATORS = [
    r"(?=\n#{1,6}\s)",  # Markdown headings
    r"\n\n+",           # Paragraph breaks
    r"\n+",             # Line breaks
    r"(?<=[.!?])\s+",   # Sentence boundaries
    r"(?<=[;:,])\s+",   # Clause boundaries
    r"\s+",             # Word boundaries
]


def chunk_text(
    text: str, max_chars: int = 1200, overlap: int | None = None
) -> list[str]:
    """Recursively split text using markdown and sentence boundaries with 10-15% overlap."""
    if max_chars <= 0:
        raise ValueError("Require max_chars > 0")
    if overlap is None:
        overlap = int(max_chars * 0.125)  # 12.5% default overlap
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("Require max_chars > overlap >= 0")

    normalized = text.strip()
    if not normalized:
        return []

    # If simple whitespace with no linebreaks or punctuation, normalize spaces
    if "\n" not in text and not re.search(r"[.!?]", text):
        normalized = " ".join(text.split())
        if not normalized:
            return []

    def _split(t: str, idx: int) -> list[str]:
        if len(t) <= max_chars:
            return [t]
        if idx >= len(SEPARATORS):
            return [t[i : i + max_chars] for i in range(0, len(t), max_chars)]
        splits = re.split(SEPARATORS[idx], t)
        if len(splits) <= 1:
            return _split(t, idx + 1)
        res = []
        for s in splits:
            if not s:
                continue
            if len(s) <= max_chars:
                res.append(s)
            else:
                res.extend(_split(s, idx + 1))
        return res

    parts = _split(normalized, 0)
    if not parts:
        return []

    chunks: list[str] = []
    current = parts[0]
    for p in parts[1:]:
        sep = "" if current.endswith(("\n", " ")) or p.startswith(("\n", " ")) else " "
        candidate = current + sep + p
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            if overlap > 0:
                overlap_prefix = current[-overlap:]
                needs_space = not (
                    overlap_prefix.endswith(("\n", " ")) or p.startswith(("\n", " "))
                )
                c_sep = " " if needs_space else ""
                current = overlap_prefix + c_sep + p
                if len(current) > max_chars:
                    current = current[:max_chars]
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks
