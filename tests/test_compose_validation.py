import importlib.util
from pathlib import Path


def test_compose_validation_script_imports_and_defines_required_services():
    script = Path(__file__).parents[1] / "scripts" / "validate_compose.py"
    spec = importlib.util.spec_from_file_location("validate_compose", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert {"db", "migrate", "uploads-init", "api", "worker"} == module.REQUIRED_SERVICES
    assert module.COMPOSE_FILE.exists()
