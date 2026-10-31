import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.integrations import google, google_api
from app.main import app
from app.persistence.models import IntegrationConnectionRow
from app.persistence.session import SessionLocal


def test_google_credentials_are_encrypted_and_require_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(google, "get_settings", lambda: type("Settings", (), {"google_token_encryption_key": key})())
    encrypted = google.encrypt_credentials({"access_token": "secret-token"})
    assert "secret-token" not in encrypted
    assert google.decrypt_credentials(encrypted) == {"access_token": "secret-token"}

    monkeypatch.setattr(
        google,
        "get_settings",
        lambda: type("Settings", (), {"google_token_encryption_key": None})(),
    )
    with pytest.raises(HTTPException) as error:
        google.encrypt_credentials({"access_token": "secret-token"})
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_free_time_uses_real_busy_intervals(monkeypatch):
    async def fake_request(*args, **kwargs):
        return {
            "calendars": {
                "primary": {
                    "busy": [
                        {
                            "start": "2026-10-23T14:00:00Z",
                            "end": "2026-10-23T15:00:00Z",
                        }
                    ]
                }
            }
        }

    monkeypatch.setattr(google_api, "_request", fake_request)
    result = await google_api.find_free_time(
        None,
        "owner",
        datetime(2026, 10, 23, 12, tzinfo=UTC),
        datetime(2026, 10, 23, 18, tzinfo=UTC),
        "UTC",
        60,
        12,
        18,
    )
    assert result["source"] == "Google Calendar freeBusy"
    assert all(
        slot["start"] != "2026-10-23T14:00:00+00:00" and slot["start"] != "2026-10-23T14:30:00+00:00"
        for slot in result["slots"]
    )
    assert not any(slot["start"] < "2026-10-23T15:00:00+00:00" < slot["end"] for slot in result["slots"])


def test_google_oauth_state_is_owner_bound_one_time_and_credentials_are_encrypted(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        google,
        "get_settings",
        lambda: SimpleNamespace(
            google_oauth_client_id="client-id",
            google_oauth_client_secret="client-secret",
            google_oauth_callback_url="https://app.example.test/api/v1/integrations/google/callback",
            google_token_encryption_key=key,
        ),
    )

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class GoogleClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **_kwargs):
            assert url == "https://oauth2.googleapis.com/token"
            return Response(
                {
                    "access_token": "access-secret",
                    "refresh_token": "refresh-secret",
                    "expires_in": 3600,
                    "scope": "https://www.googleapis.com/auth/calendar.readonly",
                }
            )

        async def get(self, url, **_kwargs):
            assert url == "https://openidconnect.googleapis.com/v1/userinfo"
            return Response({"email": "oauth-owner@example.test"})

    monkeypatch.setattr(google.httpx, "AsyncClient", GoogleClient)
    with TestClient(app) as client:
        authorize = client.post(
            "/api/v1/integrations/google/authorize",
            json={"capabilities": ["calendar.read"]},
        )
        assert authorize.status_code == 200
        query = parse_qs(urlparse(authorize.json()["authorization_url"]).query)
        assert query["redirect_uri"] == ["https://app.example.test/api/v1/integrations/google/callback"]
        state = query["state"][0]

        callback = client.get(
            "/api/v1/integrations/google/callback",
            params={"code": "mock-code", "state": state},
        )
        assert callback.status_code == 200
        assert callback.json()["connection"]["account_email"] == "oauth-owner@example.test"
        replay = client.get(
            "/api/v1/integrations/google/callback",
            params={"code": "mock-code", "state": state},
        )
        assert replay.status_code == 400

    async def assert_persisted_token_encrypted():
        async with SessionLocal() as db:
            row = await db.scalar(
                select(IntegrationConnectionRow).where(
                    IntegrationConnectionRow.account_email == "oauth-owner@example.test"
                )
            )
            assert row is not None
            assert "access-secret" not in row.encrypted_credentials
            assert google.decrypt_credentials(row.encrypted_credentials)["refresh_token"] == "refresh-secret"

    from sqlalchemy import select

    asyncio.run(assert_persisted_token_encrypted())


@pytest.mark.asyncio
async def test_search_drive_files_formats_results(monkeypatch):
    async def fake_request(*args, **kwargs):
        assert "drive/v3/files" in kwargs.get("url", args[4] if len(args) > 4 else "")
        return {
            "files": [
                {
                    "id": "doc123",
                    "name": "Quarterly Budget.docx",
                    "mimeType": "application/vnd.google-apps.document",
                    "modifiedTime": "2026-10-20T10:00:00Z",
                    "size": 2048,
                    "webViewLink": "https://docs.google.com/doc123",
                }
            ]
        }

    monkeypatch.setattr(google_api, "_request", fake_request)
    result = await google_api.search_drive_files(None, "owner", query="Budget", mime_type="document", limit=10)
    assert result["count"] == 1
    assert result["files"][0]["id"] == "doc123"
    assert result["files"][0]["name"] == "Quarterly Budget.docx"
    assert result["files"][0]["mime_type"] == "application/vnd.google-apps.document"


@pytest.mark.asyncio
async def test_get_drive_file_content_exports_docs(monkeypatch):
    async def fake_request(*args, **kwargs):
        url = kwargs.get("url", args[4] if len(args) > 4 else "")
        if "export" in url:
            return "This is the exported text of the quarterly budget document."
        return {
            "id": "doc123",
            "name": "Quarterly Budget.docx",
            "mimeType": "application/vnd.google-apps.document",
            "webViewLink": "https://docs.google.com/doc123",
        }

    monkeypatch.setattr(google_api, "_request", fake_request)
    result = await google_api.get_drive_file_content(None, "owner", "doc123")
    assert result["file_id"] == "doc123"
    assert result["name"] == "Quarterly Budget.docx"
    assert result["content"] == "This is the exported text of the quarterly budget document."
    assert result["truncated"] is False


def test_drive_tools_registered_in_catalog():
    from app.tools.registry import registry

    search_tool = registry.get("drive.search_files")
    assert search_tool is not None
    assert search_tool.provider_id == "google"
    assert search_tool.category == "drive"
    assert "https://www.googleapis.com/auth/drive.readonly" in search_tool.required_permissions

    content_tool = registry.get("drive.get_file_content")
    assert content_tool is not None
    assert content_tool.provider_id == "google"
    assert content_tool.category == "drive"
    assert "https://www.googleapis.com/auth/drive.readonly" in content_tool.required_permissions


@pytest.mark.asyncio
async def test_calendar_create_update_delete_events(monkeypatch):
    captured = []

    async def fake_request(_db, _user, scope, method, url, **kwargs):
        captured.append({"scope": scope, "method": method, "url": url, "json": kwargs.get("json")})
        if method == "POST":
            return {
                "id": "event_123",
                "summary": "Project Sync",
                "start": {"dateTime": "2026-10-30T10:00:00Z"},
                "end": {"dateTime": "2026-10-30T11:00:00Z"},
                "htmlLink": "https://calendar.google.com/event_123",
            }
        elif method == "PATCH":
            return {
                "id": "event_123",
                "summary": "Updated Sync",
                "start": {"dateTime": "2026-10-30T11:00:00Z"},
                "end": {"dateTime": "2026-10-30T12:00:00Z"},
                "htmlLink": "https://calendar.google.com/event_123",
            }
        return {}

    monkeypatch.setattr(google_api, "_request", fake_request)

    created = await google_api.create_event(
        None, "owner", "Project Sync", "2026-10-30T10:00:00Z", "2026-10-30T11:00:00Z", attendees=["team@example.com"]
    )
    assert created["status"] == "created"
    assert created["id"] == "event_123"

    updated = await google_api.update_event(
        None, "owner", "event_123", summary="Updated Sync", start="2026-10-30T11:00:00Z", end="2026-10-30T12:00:00Z"
    )
    assert updated["status"] == "updated"
    assert updated["summary"] == "Updated Sync"

    deleted = await google_api.delete_event(None, "owner", "event_123")
    assert deleted["status"] == "deleted"
    assert deleted["id"] == "event_123"
    assert len(captured) == 3


@pytest.mark.asyncio
async def test_gmail_send_reply_trash_modify(monkeypatch):
    captured = []

    async def fake_request(_db, _user, scope, method, url, **kwargs):
        captured.append({"scope": scope, "method": method, "url": url, "json": kwargs.get("json")})
        if "messages/send" in url:
            return {"id": "msg_999", "threadId": kwargs.get("json", {}).get("threadId", "thread_111")}
        elif "trash" in url:
            return {"id": "msg_999"}
        elif "modify" in url:
            return {"id": "msg_999", "labelIds": ["INBOX"]}
        return {}

    monkeypatch.setattr(google_api, "_request", fake_request)

    sent = await google_api.send_message(
        None, "owner", to=["user@example.com"], subject="Hello", body="Test message content"
    )
    assert sent["status"] == "sent"
    assert sent["message_id"] == "msg_999"

    replied = await google_api.reply_to_thread(
        None, "owner", thread_id="thread_111", body="Reply content", to=["user@example.com"], subject="Re: Hello"
    )
    assert replied["status"] == "sent"
    assert replied["thread_id"] == "thread_111"

    trashed = await google_api.trash_message(None, "owner", "msg_999")
    assert trashed["status"] == "trashed"

    modified = await google_api.modify_labels(None, "owner", "msg_999", remove_labels=["UNREAD"])
    assert modified["status"] == "updated"
    assert modified["labels"] == ["INBOX"]


@pytest.mark.asyncio
async def test_drive_create_update_delete_folder(monkeypatch):
    captured = []

    async def fake_request(_db, _user, scope, method, url, **kwargs):
        captured.append({"scope": scope, "method": method, "url": url, "json": kwargs.get("json")})
        if method == "POST" and "multipart" in url:
            return {
                "id": "file_456",
                "name": "Notes.txt",
                "mimeType": "text/plain",
                "webViewLink": "https://drive.google.com/file_456",
            }
        elif method == "POST":
            return {"id": "folder_789", "name": "Projects", "webViewLink": "https://drive.google.com/folder_789"}
        elif method == "PATCH" and "media" in url:
            return {"id": "file_456", "name": "Notes.txt", "webViewLink": "https://drive.google.com/file_456"}
        elif method == "PATCH":
            return {"id": "file_456", "trashed": True}
        return {}

    monkeypatch.setattr(google_api, "_request", fake_request)

    created_file = await google_api.create_drive_file(
        None, "owner", "Notes.txt", "Initial notes", mime_type="text/plain"
    )
    assert created_file["status"] == "created"
    assert created_file["file_id"] == "file_456"

    updated_file = await google_api.update_drive_file_content(None, "owner", "file_456", "Updated notes")
    assert updated_file["status"] == "updated"

    created_folder = await google_api.create_drive_folder(None, "owner", "Projects")
    assert created_folder["status"] == "created"
    assert created_folder["folder_id"] == "folder_789"

    trashed_file = await google_api.delete_drive_file(None, "owner", "file_456")
    assert trashed_file["status"] == "trashed"


def test_new_google_tools_registered_in_catalog():
    from app.tools.registry import registry

    expected_tools = [
        "calendar.list_events",
        "calendar.find_free_time",
        "calendar.create_event",
        "calendar.update_event",
        "calendar.delete_event",
        "gmail.search_messages",
        "gmail.get_thread",
        "gmail.create_draft",
        "gmail.send_draft",
        "gmail.send_message",
        "gmail.reply_to_thread",
        "gmail.trash_message",
        "gmail.modify_labels",
        "drive.search_files",
        "drive.get_file_content",
        "drive.create_file",
        "drive.update_file_content",
        "drive.delete_file",
        "drive.create_folder",
    ]
    for tool_name in expected_tools:
        tool = registry.get(tool_name)
        assert tool is not None, f"Expected {tool_name} to be registered"
        assert tool.provider_id == "google"
