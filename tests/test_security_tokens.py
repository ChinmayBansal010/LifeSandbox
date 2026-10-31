from fastapi.testclient import TestClient

from app.main import app


def test_protected_route_rejects_invalid_bearer_token(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_mode", "jwt")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_issuer", "test-issuer")
    monkeypatch.setattr(settings, "auth_audience", "test-audience")
    with TestClient(app) as client:
        response = client.get("/api/v1/memories", headers={"Authorization": "Bearer invalid.token.value"})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


def test_protected_route_rejects_empty_jwt_subject(monkeypatch):
    from datetime import UTC, datetime, timedelta

    import jwt

    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_mode", "jwt")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_issuer", "test-issuer")
    monkeypatch.setattr(settings, "auth_audience", "test-audience")
    token = jwt.encode(
        {"sub": "   ", "iss": "test-issuer", "aud": "test-audience", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "test-secret",
        algorithm="HS256",
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/memories", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"
