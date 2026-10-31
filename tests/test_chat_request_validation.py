from fastapi.testclient import TestClient

from app.main import app


def test_chat_rejects_whitespace_only_message():
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "  \n\t "})
    assert response.status_code == 422


def test_chat_rejects_message_over_character_limit():
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "x" * 12001})
    assert response.status_code == 422


def test_chat_trims_outer_whitespace_before_processing(monkeypatch):
    from app.services import chat as chat_service

    async def capture(state):
        assert state["message"] == "hello"
        return {"reply": "Hi there.", "intent": "conversation", "provider": "mock"}

    monkeypatch.setattr(chat_service.conversation_graph, "ainvoke", capture)
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "  hello  "})
    assert response.status_code == 200
