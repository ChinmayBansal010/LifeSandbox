#!/usr/bin/env python3
"""Validate required local service wiring in Docker Compose without starting Docker."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"
REQUIRED_SERVICES = {"db", "migrate", "uploads-init", "api", "worker"}


def main() -> int:
    document = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = document.get("services", {})
    failures = sorted(REQUIRED_SERVICES - set(services))
    for name in sorted(REQUIRED_SERVICES & set(services)):
        service = services[name]
        if name in {"api", "worker", "migrate"} and ".env" not in service.get("env_file", []):
            failures.append(f"{name}: .env must be loaded")
        if name in {"api", "worker", "migrate"}:
            dependencies = service.get("depends_on", {})
            if "migrate" not in dependencies and name != "migrate":
                failures.append(f"{name}: must wait for migrations")
        if name == "api" and "8000:8000" not in service.get("ports", []):
            failures.append("api: expected host port 8000 mapping")
        if name == "db" and not service.get("healthcheck"):
            failures.append("db: healthcheck is required")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Compose topology checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
