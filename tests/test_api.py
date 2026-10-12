from fastapi.testclient import TestClient

from app.main import app


def test_chat_persists_history_and_rejects_unknown_conversation():
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "Help me choose a laptop"})
        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "conversation"
        assert body["skill"] == "purchasing"
        conversation_id = body["conversation_id"]

        history = client.get(f"/api/v1/conversations/{conversation_id}/messages")
        assert history.status_code == 200
        assert [message["role"] for message in history.json()["items"]] == ["user", "assistant"]

        missing = client.get("/api/v1/conversations/not-a-real-id")
        assert missing.status_code == 404


def test_simulation_endpoint_returns_deterministic_result():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/simulations",
            json={
                "starting_savings": "1000",
                "monthly_income": "500",
                "monthly_expenses": "400",
                "months": 2,
                "scenarios": [{"name": "base"}],
            },
        )
        assert response.status_code == 200
        assert response.json()["scenarios"][0]["ending_balance"] == "1200"
