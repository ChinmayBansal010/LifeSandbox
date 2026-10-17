"""Text cleanup for user-facing speech synthesis."""

import re


def speech_text(markdown: str) -> str:
    text = re.sub(r"```.*?```", " Code block omitted. ", markdown, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.M)
    text = re.sub(r"\|", ", ", text)
    text = re.sub(r"[*_~]", "", text)
    return re.sub(r"\s+", " ", text).strip()
