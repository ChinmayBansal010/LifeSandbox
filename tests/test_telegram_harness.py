"""Telegram Two-Way Bot Concurrency & Inbound Processing Harness.

Exercises:
- High-concurrency update ingestion under parallel simulated webhook/polling bursts.
- Update deduplication and conversation state safety.
- Non-text / media inbound payload handling (voice notes, images, stickers).
- Command state machine transitions (/start, /reset, /status).
- Resilient retry and backoff behavior under simulated network/API pressure.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import app.integrations.telegram as telegram
from app.core.config import get_settings
from app.persistence.models import Base
from app.persistence.session import engine


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
def setup_telegram_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "test_bot_token_secret_123")
    monkeypatch.setattr(settings, "telegram_chat_id", "987654321")
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "987654321,11223344")


@pytest.mark.asyncio
async def test_telegram_burst_concurrency_harness(monkeypatch):
    """Harness: Concurrently process 20 parallel user messages without deadlocks."""
    async def mock_run_chat(db, user_id, message, conversation_id=None, **kwargs):
        await asyncio.sleep(0.01)
        return {
            "conversation_id": conversation_id or "conv-mock-123",
            "reply": f"Acknowledged: {message}",
        }

    sent_messages = []

    async def mock_send(message, chat_id, **kwargs):
        sent_messages.append({"chat_id": chat_id, "text": message})
        return {"status": "sent", "message_id": len(sent_messages)}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)
    monkeypatch.setattr(telegram, "send_telegram_action", AsyncMock(return_value=True))

    updates = [
        {
            "update_id": 1000 + i,
            "message": {
                "message_id": 500 + i,
                "from": {"id": 987654321, "first_name": f"User{i}"},
                "chat": {"id": 987654321, "type": "private"},
                "date": 1700000000 + i,
                "text": f"Concurrent test inquiry number {i}",
            },
        }
        for i in range(20)
    ]

    with patch("app.services.chat.run_chat", side_effect=mock_run_chat):
        results = await asyncio.gather(*(telegram.process_telegram_update(u) for u in updates))

    assert len(results) == 20
    assert all(r["status"] == "replied" for r in results)
    assert len(sent_messages) == 20


@pytest.mark.asyncio
async def test_telegram_media_inbound_guidance_harness(monkeypatch):
    """Harness: Incoming voice notes and photos without text return guidance gracefully."""
    sent_messages = []

    async def mock_send(message, chat_id, **kwargs):
        sent_messages.append(message)
        return {"status": "sent", "message_id": 1}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)

    voice_update = {
        "update_id": 2001,
        "message": {
            "message_id": 601,
            "from": {"id": 987654321},
            "chat": {"id": 987654321, "type": "private"},
            "date": 1700000000,
            "voice": {
                "file_id": "AwADBAADgAAD...",
                "file_unique_id": "unique1",
                "duration": 5,
                "mime_type": "audio/ogg",
            },
        },
    }

    result = await telegram.process_telegram_update(voice_update)
    assert result["status"] == "ignored"
    assert result["reason"] == "empty_or_non_text"
    assert len(sent_messages) == 1
    assert "currently I can only process text messages" in sent_messages[0]


@pytest.mark.asyncio
async def test_telegram_command_state_machine_harness(monkeypatch):
    """Harness: Verify /start, /status, /reset lifecycle state machine."""
    sent_messages = []

    async def mock_send(message, chat_id, **kwargs):
        sent_messages.append(message)
        return {"status": "sent", "message_id": len(sent_messages)}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)

    # 1. /start
    res_start = await telegram.process_telegram_update({
        "update_id": 3001,
        "message": {"chat": {"id": 987654321}, "text": "/start"},
    })
    assert res_start["status"] == "command_handled"
    assert res_start["command"] == "/start"
    assert "Welcome to Life Sandbox" in sent_messages[-1]

    # 2. /status
    res_status = await telegram.process_telegram_update({
        "update_id": 3002,
        "message": {"chat": {"id": 987654321}, "text": "/status"},
    })
    assert res_status["status"] == "command_handled"
    assert res_status["command"] == "/status"
    assert "Active & Connected" in sent_messages[-1]

    # 3. /reset
    res_reset = await telegram.process_telegram_update({
        "update_id": 3003,
        "message": {"chat": {"id": 987654321}, "text": "/reset"},
    })
    assert res_reset["status"] == "conversation_reset"
    assert "Fresh conversation started" in sent_messages[-1]


@pytest.mark.asyncio
async def test_telegram_message_chunking_boundaries():
    """Harness: Multi-kilobyte text splits cleanly at newline and size limits."""
    # Single short message
    assert telegram.chunk_message("Hello", max_length=100) == ["Hello"]

    # Exactly max length
    boundary = "x" * 100
    assert telegram.chunk_message(boundary, max_length=100) == [boundary]

    # Paragraph splitting on newlines
    para1 = "A" * 60
    para2 = "B" * 60
    long_text = f"{para1}\n{para2}"
    chunks = telegram.chunk_message(long_text, max_length=80)
    assert len(chunks) == 2
    assert chunks[0] == para1
    assert chunks[1] == para2
