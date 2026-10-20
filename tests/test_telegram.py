from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from app.integrations import telegram
from app.tools import catalog as _tools_catalog  # noqa: F401
from app.tools.registry import registry


def test_telegram_is_configured_logic(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"),
    )
    assert telegram.telegram_is_configured() is True

    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token=None),
    )
    assert telegram.telegram_is_configured() is False


@pytest.mark.asyncio
async def test_send_telegram_message_success(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="mock_token",
            telegram_chat_id="987654321",
        ),
    )

    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ok": True,
                "result": {
                    "message_id": 42,
                    "date": 1729468800,
                    "chat": {"id": 987654321, "first_name": "TestUser"},
                    "text": "Hello from LifeSandbox!",
                },
            }

    captured_requests = []

    class MockClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            captured_requests.append((url, kwargs.get("json")))
            return MockResponse()

    monkeypatch.setattr(telegram.httpx, "AsyncClient", MockClient)

    result = await telegram.send_telegram_message("Hello from LifeSandbox!")
    assert result["status"] == "sent"
    assert result["message_id"] == 42
    assert result["chat_id"] == "987654321"

    assert len(captured_requests) == 1
    url, body = captured_requests[0]
    assert url == "https://api.telegram.org/botmock_token/sendMessage"
    assert body["chat_id"] == "987654321"
    assert body["text"] == "Hello from LifeSandbox!"


@pytest.mark.asyncio
async def test_send_telegram_message_unconfigured_raises(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token=None, telegram_chat_id=None),
    )
    with pytest.raises(HTTPException) as exc:
        await telegram.send_telegram_message("test")
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "telegram_unconfigured"


@pytest.mark.asyncio
async def test_send_telegram_message_missing_chat_id_raises(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="token", telegram_chat_id=None),
    )
    with pytest.raises(HTTPException) as exc:
        await telegram.send_telegram_message("test")
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "telegram_chat_id_missing"


def test_telegram_tool_registered_in_catalog():
    tool = registry.get("telegram.send_message")
    assert tool is not None
    assert tool.provider_id == "telegram"
    assert tool.category == "messaging"
    assert tool.read_only is False
    assert "message" in tool.parameters["required"]
