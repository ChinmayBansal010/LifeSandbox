import runpy
import subprocess
import sys
from pathlib import Path


def test_compose_validation_script_passes_for_repository_compose():
    root = Path(__file__).parents[1]
    script = root / "scripts" / "validate_compose.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Compose topology checks passed" in result.stdout


def test_compose_validation_covers_required_services():
    script = Path(__file__).parents[1] / "scripts" / "validate_compose.py"
    namespace = runpy.run_path(str(script), run_name="compose_validation_test")
    assert {"db", "migrate", "uploads-init", "api", "worker"} == namespace["REQUIRED_SERVICES"]
