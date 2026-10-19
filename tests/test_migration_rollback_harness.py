"""Automated Database Migration & Rollback Harness.

Validates that Alembic migrations apply cleanly to head, roll back cleanly
to base without constraint/table leaks, and re-apply idempotently.
Also checks that all declarative models in Base.metadata match migrated tables.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.persistence.models import Base

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_alembic_db(monkeypatch):
    """Provide an isolated SQLite database file specifically for Alembic migration testing."""
    with tempfile.TemporaryDirectory(prefix="life-sandbox-alembic-") as temp_dir:
        db_path = Path(temp_dir) / "alembic_test.db"
        # Alembic env.py uses async engine with get_settings().database_url
        async_url = f"sqlite+aiosqlite:///{db_path}"
        sync_url = f"sqlite:///{db_path}"

        settings = get_settings()
        monkeypatch.setattr(settings, "database_url", async_url)

        alembic_cfg = Config(str(ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(ROOT / "migrations"))
        alembic_cfg.set_main_option("sqlalchemy.url", async_url)

        yield {
            "config": alembic_cfg,
            "sync_url": sync_url,
            "db_path": db_path,
        }


def test_migration_forward_and_rollback_harness(isolated_alembic_db):
    """Harness: test forward migration to head, full rollback to base, and re-upgrade."""
    cfg = isolated_alembic_db["config"]
    sync_url = isolated_alembic_db["sync_url"]

    # 1. Forward migration to head
    command.upgrade(cfg, "head")

    sync_engine = create_engine(sync_url)
    inspector = inspect(sync_engine)
    head_tables = set(inspector.get_table_names())

    # Assert expected core tables exist after upgrade head
    expected_tables = {
        "conversations",
        "messages",
        "memories",
        "files",
        "integration_connections",
        "google_login_states",
        "google_oauth_states",
        "tasks",
        "reminders",
        "projects",
        "action_approvals",
    }
    assert expected_tables.issubset(head_tables), f"Missing tables: {expected_tables - head_tables}"

    # 2. Rollback step-by-step or to base
    command.downgrade(cfg, "base")

    inspector = inspect(sync_engine)
    base_tables = set(inspector.get_table_names())
    # After downgrade to base, application tables should be dropped (alembic_version may remain)
    assert not expected_tables.intersection(
        base_tables
    ), f"Tables remained after downgrade to base: {expected_tables.intersection(base_tables)}"

    # 3. Idempotent re-upgrade to head
    command.upgrade(cfg, "head")

    inspector = inspect(sync_engine)
    reupgraded_tables = set(inspector.get_table_names())
    assert expected_tables.issubset(reupgraded_tables)


def test_migration_schema_matches_declarative_models(isolated_alembic_db):
    """Harness: verify every SQLAlchemy model table in Base.metadata is created by migrations."""
    cfg = isolated_alembic_db["config"]
    sync_url = isolated_alembic_db["sync_url"]

    command.upgrade(cfg, "head")

    sync_engine = create_engine(sync_url)
    inspector = inspect(sync_engine)
    db_tables = set(inspector.get_table_names())

    model_tables = set(Base.metadata.tables.keys())
    missing_in_db = model_tables - db_tables

    assert not missing_in_db, (
        "Schema drift detected! Tables declared in Base.metadata "
        f"but missing from migrations: {missing_in_db}"
    )
