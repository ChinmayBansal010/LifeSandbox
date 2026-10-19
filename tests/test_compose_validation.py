import runpy
from pathlib import Path


def test_compose_validation_script_runs_successfully():
    root = Path(__file__).parents[1]
    script = root / "scripts" / "validate_compose.py"
    namespace = runpy.run_path(str(script), run_name="compose_validation_test")
    assert {"db", "migrate", "uploads-init", "api", "worker"} == namespace["REQUIRED_SERVICES"]


def test_compose_validation_script_passes_for_repository_compose(monkeypatch):
    import runpy
    import sys

    root = Path(__file__).parents[1]
    script = root / "scripts" / "validate_compose.py"
    monkeypatch.setattr(sys, "argv", [str(script)])
    namespace = runpy.run_path(str(script), run_name="__main__")
    assert namespace["COMPOSE_FILE"].is_file()
