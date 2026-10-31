from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_does_not_expose_environment_configuration():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "environment" not in response.json()


def test_request_id_header_is_preserved():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-request-123"})
    assert response.headers["X-Request-ID"] == "test-request-123"


def test_request_id_rejects_untrusted_header_values():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "bad\\r\\nInjected: yes"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "bad\\r\\nInjected: yes"


def test_request_id_is_generated_when_missing():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_chat_rejects_empty_message_before_processing():
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_rejects_message_over_documented_limit():
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "x" * 12001})
    assert response.status_code == 422


def test_chat_rejects_too_many_attachments():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "summarize these", "attachment_ids": ["f"] * 6},
        )
    assert response.status_code == 422


def test_chat_rejects_excessive_history():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "hello", "history": [{"role": "user", "content": "hi"}] * 13},
        )
    assert response.status_code == 422
