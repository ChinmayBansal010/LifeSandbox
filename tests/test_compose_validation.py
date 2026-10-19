import subprocess
import sys
from pathlib import Path


def test_compose_validation_passes_for_repository_compose():
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
