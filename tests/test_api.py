from fastapi.testclient import TestClient

from app.main import app
from app.providers.llm import LLMError
from app.services import chat as chat_service


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


def test_plugin_catalogue_is_registry_backed_and_reports_setup_truthfully():
    with TestClient(app) as client:
        response = client.get("/api/v1/plugins")
    assert response.status_code == 200
    tools = {item["id"]: item for item in response.json()["tools"]}
    assert "gmail.search_messages" in tools
    assert tools["gmail.search_messages"]["status"] == "requires_setup"
    assert tools["gmail.search_messages"]["provider"] == "google"
    assert "gmail.readonly" in tools["gmail.search_messages"]["permission_requirements"][0]
    assert {item["status"] for item in tools.values()} <= {
        "available", "connected", "requires_setup", "requires_connection",
        "permission_required", "disabled", "unavailable", "degraded",
    }
    assert all("token" not in key.lower() for item in tools.values() for key in item)


def test_chat_reports_provider_errors_as_gateway_errors(monkeypatch):
    async def fail_with_rate_limit(_state):
        raise LLMError("openrouter returned HTTP 429", provider="openrouter", status_code=429)

    monkeypatch.setattr(chat_service.conversation_graph, "ainvoke", fail_with_rate_limit)
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "hello"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_provider_error"
    assert response.json()["error"]["upstream_status"] == 429


def test_openrouter_timeout_contract_marks_mem0_not_attempted(monkeypatch):
    async def fail_with_timeout(_state):
        raise LLMError("request timed out", provider="openrouter", code="timeout")

    monkeypatch.setattr(chat_service.conversation_graph, "ainvoke", fail_with_timeout)
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "hello", "remember": True})

    assert response.status_code == 504
    body = response.json()["error"]
    assert body["mem0_opt_in"] is True
    assert body["mem0_save_status"] == "not_attempted"
    assert body["failure_detail"]["provider"] == "openrouter"
    assert body["failure_detail"]["stage"] == "llm_generate"
    assert body["failure_detail"]["code"] == "timeout"


def test_conversation_crud_lifecycle_and_messages():
    with TestClient(app) as client:
        # 1. Create a conversation
        create_res = client.post("/api/v1/conversations")
        assert create_res.status_code == 201
        created = create_res.json()
        conv_id = created["id"]
        assert created["title"] == "New conversation"

        # 2. List conversations includes created conversation
        list_res = client.get("/api/v1/conversations")
        assert list_res.status_code == 200
        items = list_res.json()["items"]
        assert any(item["id"] == conv_id for item in items)

        # 3. Rename conversation
        rename_res = client.patch(
            f"/api/v1/conversations/{conv_id}",
            json={"title": "Updated Strategy Session"},
        )
        assert rename_res.status_code == 200
        assert rename_res.json()["title"] == "Updated Strategy Session"

        # 4. Fetch renamed conversation
        get_res = client.get(f"/api/v1/conversations/{conv_id}")
        assert get_res.status_code == 200
        assert get_res.json()["title"] == "Updated Strategy Session"

        # 5. Insert messages directly to verify /messages endpoint
        from app.persistence.session import SessionLocal
        from app.persistence.models import MessageRow
        import asyncio

        async def _add_msgs():
            async with SessionLocal() as db:
                db.add(MessageRow(conversation_id=conv_id, role="user", content="What should I focus on first?"))
                db.add(MessageRow(conversation_id=conv_id, role="assistant", content="Focus on core architecture."))
                await db.commit()

        asyncio.run(_add_msgs())

        # 6. Verify messages endpoint returns ordered messages
        msg_res = client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert msg_res.status_code == 200
        msg_items = msg_res.json()["items"]
        assert len(msg_items) == 2
        assert msg_items[0]["role"] == "user"
        assert msg_items[0]["content"] == "What should I focus on first?"
        assert msg_items[1]["role"] == "assistant"
        assert msg_items[1]["content"] == "Focus on core architecture."

        # 7. Delete conversation
        del_res = client.delete(f"/api/v1/conversations/{conv_id}")
        assert del_res.status_code == 204

        # 8. Verify it is no longer found
        assert client.get(f"/api/v1/conversations/{conv_id}").status_code == 404
        assert client.get(f"/api/v1/conversations/{conv_id}/messages").status_code == 404

