from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.integrations import telegram
from app.main import app
from app.persistence.models import Base
from app.persistence.session import engine


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


def test_is_chat_allowed_logic(monkeypatch):
    # Case 1: Both telegram_allowed_chat_ids and telegram_chat_id provided
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="token",
            telegram_chat_id="11111",
            telegram_allowed_chat_ids="22222, 33333",
        ),
    )
    assert telegram.is_chat_allowed("11111") is True
    assert telegram.is_chat_allowed(22222) is True
    assert telegram.is_chat_allowed("33333") is True
    assert telegram.is_chat_allowed("99999") is False
    assert telegram.is_chat_allowed(None) is False

    # Case 2: Only telegram_chat_id
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="token",
            telegram_chat_id="11111",
            telegram_allowed_chat_ids=None,
        ),
    )
    assert telegram.is_chat_allowed("11111") is True
    assert telegram.is_chat_allowed("99999") is False

    # Case 3: Nothing configured -> deny all for security
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="token",
            telegram_chat_id=None,
            telegram_allowed_chat_ids=None,
        ),
    )
    assert telegram.is_chat_allowed("11111") is False


def test_chunk_message():
    short_text = "Hello world"
    assert telegram.chunk_message(short_text) == ["Hello world"]

    # Exactly 4000 characters
    medium_text = "a" * 4000
    assert len(telegram.chunk_message(medium_text)) == 1

    # Over 4000 characters
    long_text = ("Hello line\n" * 500)
    chunks = telegram.chunk_message(long_text, max_length=1000)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1000


@pytest.mark.asyncio
async def test_send_telegram_action(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="test_token"),
    )

    class MockResponse:
        status_code = 200

    captured = []

    class MockClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            captured.append((url, kwargs.get("json")))
            return MockResponse()

    monkeypatch.setattr(telegram.httpx, "AsyncClient", MockClient)

    ok = await telegram.send_telegram_action("12345", "typing")
    assert ok is True
    assert len(captured) == 1
    assert captured[0][0] == "https://api.telegram.org/bottest_token/sendChatAction"
    assert captured[0][1] == {"chat_id": "12345", "action": "typing"}


@pytest.mark.asyncio
async def test_process_telegram_update_unauthorized(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="mock_token",
            telegram_chat_id="11111",
            telegram_allowed_chat_ids=None,
            telegram_default_user_id="local-user",
        ),
    )

    sent_messages = []

    async def mock_send(message, chat_id=None, parse_mode="HTML"):
        sent_messages.append({"message": message, "chat_id": chat_id})
        return {"status": "sent", "message_id": 1, "chat_id": str(chat_id)}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)

    unauthorized_update = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": 99999},
            "text": "Hello there",
        },
    }

    result = await telegram.process_telegram_update(unauthorized_update)
    assert result["status"] == "unauthorized"
    assert result["chat_id"] == "99999"
    assert len(sent_messages) == 1
    assert "Access Denied" in sent_messages[0]["message"]


@pytest.mark.asyncio
async def test_process_telegram_update_start_command(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="mock_token",
            telegram_chat_id="11111",
            telegram_allowed_chat_ids=None,
            telegram_default_user_id="local-user",
        ),
    )

    sent_messages = []

    async def mock_send(message, chat_id=None, parse_mode="HTML"):
        sent_messages.append({"message": message, "chat_id": chat_id})
        return {"status": "sent", "message_id": 1, "chat_id": str(chat_id)}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)

    update = {
        "update_id": 2,
        "message": {
            "message_id": 11,
            "chat": {"id": 11111},
            "text": "/start",
        },
    }

    result = await telegram.process_telegram_update(update)
    assert result["status"] == "command_handled"
    assert result["command"] == "/start"
    assert len(sent_messages) == 1
    assert "Welcome to Life Sandbox" in sent_messages[0]["message"]


@pytest.mark.asyncio
async def test_process_telegram_update_chat_flow(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="mock_token",
            telegram_chat_id="11111",
            telegram_allowed_chat_ids=None,
            telegram_default_user_id="local-user",
            llm_provider="mock",
        ),
    )

    sent_messages = []

    async def mock_send(message, chat_id=None, parse_mode="HTML"):
        sent_messages.append({"message": message, "chat_id": chat_id})
        return {"status": "sent", "message_id": 1, "chat_id": str(chat_id)}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)
    monkeypatch.setattr(telegram, "send_telegram_action", AsyncMock(return_value=True))

    async def mock_run_chat(db, user_id, message, conversation_id=None, **kwargs):
        assert user_id == "local-user"
        assert message == "Plan my week"
        assert conversation_id is not None
        return {
            "conversation_id": conversation_id,
            "reply": "Here is your weekly plan outline.",
        }

    with patch("app.services.chat.run_chat", side_effect=mock_run_chat):
        update = {
            "update_id": 3,
            "message": {
                "message_id": 12,
                "chat": {"id": 11111},
                "text": "Plan my week",
            },
        }

        result = await telegram.process_telegram_update(update)
        assert result["status"] == "replied"
        assert result["chat_id"] == "11111"
        assert len(sent_messages) == 1
        assert sent_messages[0]["message"] == "Here is your weekly plan outline."


def test_telegram_webhook_route(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="mock_token",
            telegram_chat_id="11111",
            telegram_allowed_chat_ids=None,
            telegram_default_user_id="local-user",
            telegram_webhook_secret="super_secret_token",
        ),
    )

    with TestClient(app) as client:
        # Invalid secret token
        res_bad = client.post(
            "/api/v1/integrations/telegram/webhook",
            json={"update_id": 1, "message": {"chat": {"id": 11111}, "text": "/help"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )
        assert res_bad.status_code == 403

        # Valid secret token
        async def mock_process(update, db=None):
            return {"status": "mocked"}

        monkeypatch.setattr(telegram, "process_telegram_update", mock_process)

        res_good = client.post(
            "/api/v1/integrations/telegram/webhook",
            json={"update_id": 1, "message": {"chat": {"id": 11111}, "text": "/help"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "super_secret_token"},
        )
        assert res_good.status_code == 200
        assert res_good.json()["ok"] is True
