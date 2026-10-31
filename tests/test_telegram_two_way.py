from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import Principal, current_principal
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
    long_text = "Hello line\n" * 500
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

        app.dependency_overrides[current_principal] = lambda: Principal(user_id="ordinary-user")
        try:
            res_set = client.post(
                "/api/v1/integrations/telegram/set-webhook",
                json={"webhook_url": "https://example.com/hook"},
            )
            res_delete = client.post("/api/v1/integrations/telegram/delete-webhook")
            assert res_set.status_code == 403
            assert res_delete.status_code == 403
        finally:
            app.dependency_overrides.pop(current_principal, None)


@pytest.mark.asyncio
async def test_telegram_connect_google_command(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="mock_token",
            telegram_chat_id="11111",
            telegram_allowed_chat_ids=None,
            telegram_default_user_id="local-user",
            google_oauth_client_id="client_id",
            google_oauth_client_secret="client_secret",
            google_oauth_callback_url="http://localhost:8000/callback",
            google_token_encryption_key="mock_key",
        ),
    )

    sent = []

    async def mock_send(message, chat_id=None, parse_mode="HTML"):
        sent.append(message)
        return {"status": "sent"}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)

    async def mock_auth_url(user_id, db):
        return "https://accounts.google.com/o/oauth2/v2/auth?state=mock"

    monkeypatch.setattr(telegram, "create_google_authorization_url", mock_auth_url)

    update = {"update_id": 4, "message": {"message_id": 20, "chat": {"id": 11111}, "text": "/connect_google"}}
    res = await telegram.process_telegram_update(update)
    assert res["status"] == "command_handled"
    assert len(sent) == 1
    assert "accounts.google.com" in sent[0]


@pytest.mark.asyncio
async def test_telegram_approvals_and_approve_reject_flow(monkeypatch):
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

    sent = []

    async def mock_send(message, chat_id=None, parse_mode="HTML"):
        sent.append(message)
        return {"status": "sent"}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)

    # 1. Check /approvals when empty
    update_empty = {"update_id": 5, "message": {"message_id": 21, "chat": {"id": 11111}, "text": "/approvals"}}
    res = await telegram.process_telegram_update(update_empty)
    assert res["status"] == "command_handled"
    assert "No pending approvals" in sent[-1]

    # 2. Add a pending approval to DB
    import hashlib

    from app.persistence.models import ApprovalRow
    from app.persistence.session import SessionLocal

    args = '{"test": "arg"}'
    approval_id = "test-appr-123"
    async with SessionLocal() as db:
        db.add(
            ApprovalRow(
                id=approval_id,
                user_id="local-user",
                action="gmail.send_draft",
                description="Send email to user@test.com",
                arguments=args,
                payload_hash=hashlib.sha256(args.encode()).hexdigest(),
                status="pending",
            )
        )
        await db.commit()

    # 3. Check /approvals lists the pending approval
    update_list = {"update_id": 6, "message": {"message_id": 22, "chat": {"id": 11111}, "text": "/pending"}}
    res = await telegram.process_telegram_update(update_list)
    assert res["status"] == "command_handled"
    assert approval_id in sent[-1]

    # 4. Mock approval execution
    async def mock_exec_approval(db, user_id, approval_id, correlation_id=None, allow_pending=False):
        return {"status": "succeeded", "resource_type": "google_message", "message_id": "sent-msg-1"}

    with patch("app.api.workflow.execute_approval_action", side_effect=mock_exec_approval):
        update_approve = {
            "update_id": 7,
            "message": {"message_id": 23, "chat": {"id": 11111}, "text": f"/approve {approval_id}"},
        }
        res_approve = await telegram.process_telegram_update(update_approve)
        assert res_approve["status"] == "approval_executed"
        assert "Action Approved and Executed" in sent[-1]


def test_extract_oauth_code_and_state():
    # Full callback URL
    url = (
        "http://localhost:8000/api/v1/integrations/google/callback?code=test-code-123&state=test-state-456&scope=openid"
    )
    code, state = telegram.extract_oauth_code_and_state(url)
    assert code == "test-code-123"
    assert state == "test-state-456"

    # Command prefix /callback
    cmd = f"/callback {url}"
    code, state = telegram.extract_oauth_code_and_state(cmd)
    assert code == "test-code-123"
    assert state == "test-state-456"

    # Encoded parameters
    url_enc = "http://localhost:8000/callback?state=my%20state&code=my%2Fcode"
    code, state = telegram.extract_oauth_code_and_state(url_enc)
    assert code == "my/code"
    assert state == "my state"

    # Plain query string
    code, state = telegram.extract_oauth_code_and_state("code=abc&state=xyz")
    assert code == "abc"
    assert state == "xyz"

    # Invalid / unrelated text
    assert telegram.extract_oauth_code_and_state("hello world") == (None, None)
    assert telegram.extract_oauth_code_and_state("/callback") == (None, None)


@pytest.mark.asyncio
async def test_telegram_google_callback_pasted_url(monkeypatch):
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

    sent = []

    async def mock_send(message, chat_id=None, parse_mode="HTML"):
        sent.append(message)
        return {"status": "sent"}

    monkeypatch.setattr(telegram, "send_telegram_message", mock_send)

    # 1. Bare /callback command
    update_bare = {"update_id": 8, "message": {"message_id": 24, "chat": {"id": 11111}, "text": "/callback"}}
    res_bare = await telegram.process_telegram_update(update_bare)
    assert res_bare["status"] == "command_handled"
    assert "How to Complete Connection" in sent[-1]

    # 2. Pasted callback URL succeeds
    async def mock_complete_callback(code, state, db):
        return {
            "connected": True,
            "account_email": "user@example.com",
            "token_scopes": ["https://www.googleapis.com/auth/calendar"],
            "message": "Connected",
        }

    monkeypatch.setattr(telegram, "complete_google_callback", mock_complete_callback)

    callback_url = "http://localhost:8000/api/v1/integrations/google/callback?state=my_state&code=my_code"
    update_pasted = {"update_id": 9, "message": {"message_id": 25, "chat": {"id": 11111}, "text": callback_url}}
    res_pasted = await telegram.process_telegram_update(update_pasted)
    assert res_pasted["status"] == "google_connected"
    assert res_pasted["account_email"] == "user@example.com"
    assert "Google Account Connected Successfully" in sent[-1]
    assert "user@example.com" in sent[-1]


def test_sanitize_telegram_response_and_formatting():
    sample_openui = (
        "I can help you think through this decision! Let me structure a comparison of the "
        "two paths using the OpenUI framework so you can see the key dimensions side by side.\n\n"
        "Let me first check if I need to reference any data about these fields, and then I'll present a comparison.\n\n"
        "Actually, let me just build a comprehensive comparison directly — I have enough "
        "understanding of both fields to present the key trade-offs.\n\n"
        "Let me structure this as a comparison with KPI cards and a decision framework.\n"
        "root = Card([header, kpiBlock, comparisonSections, decisionFactors, actionButtons])\n"
        'header = CardHeader("CSE vs VLSI: Career Comparison", "Key dimensions to help you decide")\n'
        'cseMarket = TextContent("**Job Market:** Huge demand across software, AI, data, full-stack.")\n'
        'vlsiMarket = TextContent("**Job Market:** Narrower but specialized in chip design.")\n'
        'decisionFactors = InlineHeader("Decision Framework", "Rate these factors for yourself")\n'
    )
    sanitized = telegram.sanitize_telegram_response(sample_openui)
    # Ensure raw OpenUI assignments and internal monologue are stripped
    assert "root = Card" not in sanitized
    assert "TextContent(" not in sanitized
    assert "Actually, let me just build" not in sanitized
    # Ensure title and content are preserved in clean markdown
    assert "CSE vs VLSI: Career Comparison" in sanitized
    assert "**Job Market:** Huge demand across software" in sanitized
    assert "Decision Framework" in sanitized

    formatted = telegram.format_markdown_for_telegram(sample_openui)
    assert "<b>Job Market:</b>" in formatted
    assert "root = Card" not in formatted


@pytest.mark.asyncio
async def test_process_telegram_update_passes_channel(monkeypatch):
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
    monkeypatch.setattr(telegram, "send_telegram_message", AsyncMock(return_value={"status": "sent"}))
    monkeypatch.setattr(telegram, "send_telegram_action", AsyncMock(return_value=True))

    passed_kwargs = {}

    async def mock_run_chat(db, user_id, message, conversation_id=None, **kwargs):
        passed_kwargs.update(kwargs)
        return {"conversation_id": conversation_id, "reply": "Clean response"}

    with patch("app.services.chat.run_chat", side_effect=mock_run_chat):
        update = {
            "update_id": 10,
            "message": {
                "message_id": 30,
                "chat": {"id": 11111},
                "text": "CSE or VLSI?",
            },
        }
        await telegram.process_telegram_update(update)
        assert passed_kwargs.get("channel") == "telegram"


def test_telegram_chat_tenant_isolation(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_chat_id="11111",
            telegram_allowed_chat_ids="22222,33333",
            telegram_default_user_id="local-user",
            telegram_user_id_map={},
        ),
    )
    assert telegram.telegram_user_id_for_chat("22222") == "telegram:22222"
    assert telegram.telegram_user_id_for_chat("33333") == "telegram:33333"

    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_chat_id="11111",
            telegram_allowed_chat_ids=None,
            telegram_default_user_id="google:trusted-user",
            telegram_user_id_map={"11111": "google:trusted-user"},
        ),
    )
    assert telegram.telegram_user_id_for_chat("11111") == "google:trusted-user"


@pytest.mark.asyncio
async def test_telegram_group_chat_is_rejected(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="token",
            telegram_chat_id="-100123",
            telegram_allowed_chat_ids=None,
            telegram_default_user_id="local-user",
        ),
    )
    result = await telegram.process_telegram_update(
        {
            "update_id": 91,
            "message": {
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 12345},
                "text": "/status",
            },
        }
    )
    assert result["status"] == "unauthorized"
