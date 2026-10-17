"""Force the API suite onto isolated local settings, regardless of a developer's .env."""

import os
import tempfile
from pathlib import Path

os.environ["APP_ENV"] = "development"
os.environ["AUTH_MODE"] = "development"
_test_database_directory = tempfile.TemporaryDirectory(prefix="life-sandbox-tests-")
_test_database_path = Path(_test_database_directory.name) / "test.db"
os.environ["DATABASE_URL"] = os.environ.get(
    "LIFESANDBOX_TEST_DATABASE_URL", f"sqlite+aiosqlite:///{_test_database_path}"
)
os.environ["LLM_PROVIDER"] = "mock"
