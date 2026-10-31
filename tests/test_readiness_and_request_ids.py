from fastapi.testclient import TestClient

from app.main import app


def test_request_id_is_returned_and_preserves_supplied_value():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "qa-request-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "qa-request-123"


def test_request_id_is_generated_when_not_supplied():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-request-id")


def test_readiness_returns_database_status():
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
