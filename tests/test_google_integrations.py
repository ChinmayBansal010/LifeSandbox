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
    monkeypatch.setattr(
        google, "get_settings", lambda: type("Settings", (), {"google_token_encryption_key": key})()
    )
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
        slot["start"] != "2026-10-23T14:00:00+00:00"
        and slot["start"] != "2026-10-23T14:30:00+00:00"
        for slot in result["slots"]
    )
    assert not any(
        slot["start"] < "2026-10-23T15:00:00+00:00" < slot["end"] for slot in result["slots"]
    )


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
        assert query["redirect_uri"] == [
            "https://app.example.test/api/v1/integrations/google/callback"
        ]
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
            assert (
                google.decrypt_credentials(row.encrypted_credentials)["refresh_token"]
                == "refresh-secret"
            )

    from sqlalchemy import select

    asyncio.run(assert_persisted_token_encrypted())
