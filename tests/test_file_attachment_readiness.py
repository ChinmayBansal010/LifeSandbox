import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.jobs.worker import run_due_jobs
from app.main import app, settings
from app.persistence.models import FileChunkRow, FileRow, JobRow
from app.persistence.session import SessionLocal
from app.services.files import process_document_ingestion


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "file_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "llm_provider", "mock")
    monkeypatch.setattr(settings, "embedding_provider", "local_hash")
    monkeypatch.setattr(settings, "embedding_dimensions", 64)


def test_file_status_endpoint_returns_accurate_metadata(tmp_path):
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/v1/files",
            files={"file": ("project_spec.txt", b"LifeSandbox Specification Document", "text/plain")},
        )
        assert uploaded.status_code == 201
        data = uploaded.json()
        file_id = data["id"]
        assert data["filename"] == "project_spec.txt"
        assert data["status"] in {"processing", "ready"}

        status_res = client.get(f"/api/v1/files/{file_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["id"] == file_id
        assert status_data["filename"] == "project_spec.txt"
        assert status_data["mime_type"] == "text/plain"
        assert status_data["size_bytes"] == len(b"LifeSandbox Specification Document")
        assert "created_at" in status_data
        assert "download_available" in status_data
        assert "error_message" in status_data


def test_file_status_endpoint_returns_404_for_unknown():
    with TestClient(app) as client:
        res = client.get(f"/api/v1/files/{uuid.uuid4()}")
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_successful_ingestion_transitions_to_ready(tmp_path):
    file_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    test_file_path = tmp_path / file_id
    content = "Architecture: System uses fast vector embeddings and pgvector storage."
    test_file_path.write_bytes(content.encode("utf-8"))

    async with SessionLocal() as db:
        file_row = FileRow(
            id=file_id,
            user_id=user_id,
            filename="arch.txt",
            mime_type="text/plain",
            size_bytes=len(content),
            status="processing",
            storage_key=file_id,
        )
        db.add(file_row)
        await db.commit()

        count = await process_document_ingestion(db, file_id, user_id)
        assert count >= 1

        updated = await db.get(FileRow, file_id)
        assert updated is not None
        assert updated.status == "ready"
        assert updated.error_message is None

        chunks = list(
            (await db.scalars(select(FileChunkRow).where(FileChunkRow.file_id == file_id))).all()
        )
        assert len(chunks) == count
        assert chunks[0].embedding is not None


@pytest.mark.asyncio
async def test_extraction_failure_transitions_to_durable_error_state(tmp_path):
    file_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    test_file_path = tmp_path / file_id
    # Empty content causes ValueError("No extractable text was found in this document")
    test_file_path.write_bytes(b"   \n\n   ")

    async with SessionLocal() as db:
        file_row = FileRow(
            id=file_id,
            user_id=user_id,
            filename="empty.txt",
            mime_type="text/plain",
            size_bytes=8,
            status="processing",
            storage_key=file_id,
        )
        db.add(file_row)
        await db.commit()

        with pytest.raises(ValueError, match="No extractable text"):
            await process_document_ingestion(db, file_id, user_id)

        updated = await db.get(FileRow, file_id)
        assert updated is not None
        assert updated.status == "error"
        assert "No extractable text" in (updated.error_message or "")


def test_chat_rejects_unready_attachments_with_422(tmp_path):
    with TestClient(app) as client:
        # Create a file directly with status="processing"
        file_id = str(uuid.uuid4())
        user_id = "local-user"  # development auth default

        async def insert_processing_file():
            async with SessionLocal() as db:
                file_row = FileRow(
                    id=file_id,
                    user_id=user_id,
                    filename="processing.txt",
                    mime_type="text/plain",
                    size_bytes=100,
                    status="processing",
                    storage_key=file_id,
                )
                db.add(file_row)
                await db.commit()

        import asyncio
        asyncio.run(insert_processing_file())

        response = client.post(
            "/api/v1/chat",
            json={"message": "Summarize this document", "attachment_ids": [file_id]},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_attachment"
        assert "not ready" in response.json()["detail"]["message"].lower()


def test_chat_rejects_failed_attachments_with_422():
    with TestClient(app) as client:
        file_id = str(uuid.uuid4())
        user_id = "local-user"

        async def insert_failed_file():
            async with SessionLocal() as db:
                file_row = FileRow(
                    id=file_id,
                    user_id=user_id,
                    filename="corrupted.pdf",
                    mime_type="application/pdf",
                    size_bytes=100,
                    status="error",
                    error_message="Document is corrupted",
                    storage_key=file_id,
                )
                db.add(file_row)
                await db.commit()

        import asyncio
        asyncio.run(insert_failed_file())

        response = client.post(
            "/api/v1/chat",
            json={"message": "Read corrupted doc", "attachment_ids": [file_id]},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_attachment"


def test_chat_rejects_nonexistent_attachment_ids_with_422():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Read missing doc", "attachment_ids": [str(uuid.uuid4())]},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_attachment"


def test_retry_file_ingestion_endpoint(tmp_path):
    with TestClient(app) as client:
        file_id = str(uuid.uuid4())
        user_id = "local-user"
        test_file_path = tmp_path / file_id
        test_file_path.write_bytes(b"Recovered file content for ingestion retry.")

        async def insert_error_file():
            async with SessionLocal() as db:
                file_row = FileRow(
                    id=file_id,
                    user_id=user_id,
                    filename="retry_me.txt",
                    mime_type="text/plain",
                    size_bytes=42,
                    status="error",
                    error_message="Worker timeout during previous run",
                    storage_key=file_id,
                )
                db.add(file_row)
                await db.commit()

        import asyncio
        asyncio.run(insert_error_file())

        retry_res = client.post(f"/api/v1/files/{file_id}/retry")
        assert retry_res.status_code == 200
        data = retry_res.json()
        assert data["id"] == file_id
        assert data["status"] in {"processing", "ready"}
        assert data["error_message"] is None
