#!/usr/bin/env python3
"""Fail on common accidental secret and generated-file inclusions."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKED = (
    subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    .stdout.decode()
    .split("\0")
)
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "common API token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,}|"
        r"sk-or-v1-[A-Fa-f0-9]{40,})\b"
    ),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
ALLOWED_SECRET_FIXTURES = {
    ".env.example",
}


def main() -> int:
    failures: list[str] = []
    for relative in TRACKED:
        if not relative:
            continue
        path = ROOT / relative
        lower = relative.lower()
        generated_dirs = {".venv", "node_modules", "__pycache__", ".pytest_cache"}
        if any(part in generated_dirs for part in path.parts):
            failures.append(f"{relative}: generated directory is tracked")
            continue
        if lower.endswith((".pem", ".key", ".p12", ".pfx", ".sqlite", ".db")):
            failures.append(f"{relative}: sensitive or runtime artifact is tracked")
            continue
        if relative in ALLOWED_SECRET_FIXTURES or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                failures.append(f"{relative}: possible {label} detected")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Repository hygiene passed for {sum(bool(item) for item in TRACKED)} tracked paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
