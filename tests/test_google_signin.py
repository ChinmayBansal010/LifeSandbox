from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import app.api.auth as auth_module
import app.core.security as security_module
from app.main import app


@pytest.fixture
def signin_settings():
    return SimpleNamespace(
        google_oauth_client_id="client-id.apps.googleusercontent.com",
        google_oauth_client_secret="client-secret",
        google_auth_callback_url="http://localhost:8000/api/v1/auth/google/callback",
        google_auth_frontend_url="http://localhost:5173",
        auth_secret="test-session-secret-long-enough-for-sha256",
        auth_issuer=None,
        auth_audience=None,
        auth_mode="development",
        app_env="development",
    )


def test_google_signin_creates_owner_session_and_consumes_state(monkeypatch, signin_settings):
    monkeypatch.setattr(auth_module, "get_settings", lambda: signin_settings)
    monkeypatch.setattr(security_module, "get_settings", lambda: signin_settings)

    async def exchange(_code, verifier, _settings):
        assert verifier
        return "mock-google-id-token"

    def verify(_token, _client_id, nonce):
        assert nonce
        return {
            "sub": "google-subject-123",
            "email": "person@example.com",
            "email_verified": True,
            "name": "Personal User",
        }

    monkeypatch.setattr(auth_module, "_exchange_google_code", exchange)
    monkeypatch.setattr(auth_module, "_verify_google_id_token", verify)

    with TestClient(app, follow_redirects=False) as client:
        start = client.get("/api/v1/auth/google/start")
        assert start.status_code == 302
        authorize = parse_qs(urlparse(start.headers["location"]).query)
        assert authorize["scope"] == ["openid email profile"]
        assert authorize["code_challenge_method"] == ["S256"]
        state = authorize["state"][0]
        assert start.cookies.get(auth_module.STATE_COOKIE) == state

        callback = client.get(
            "/api/v1/auth/google/callback",
            params={"code": "mock-code", "state": state},
        )
        assert callback.status_code == 303
        assert callback.headers["location"] == "http://localhost:5173/?auth=success"
        assert auth_module.SESSION_COOKIE in callback.cookies
        assert "httponly" in callback.headers["set-cookie"].lower()

        account = client.get("/api/v1/auth/me")
        assert account.status_code == 200
        assert account.json() == {
            "user_id": "google:google-subject-123",
            "email": "person@example.com",
            "name": "Personal User",
            "authenticated": True,
        }

        replay = client.get(
            "/api/v1/auth/google/callback",
            params={"code": "mock-code", "state": state},
        )
        assert replay.status_code == 400


def test_google_signin_reports_missing_server_configuration(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "get_settings",
        lambda: SimpleNamespace(
            google_oauth_client_id=None,
            google_oauth_client_secret=None,
            google_auth_callback_url=None,
            google_auth_frontend_url="http://localhost:5173",
            auth_secret=None,
        ),
    )
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/api/v1/auth/google/start")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "google_signin_unconfigured"
