import asyncio
import html
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import Principal, current_principal
from app.integrations.google import complete_google_callback, create_google_authorization_url
from app.persistence.models import (
    ApprovalRow,
    AuditRow,
    ConversationRow,
    IntegrationConnectionRow,
)
from app.persistence.session import SessionLocal, get_session

logger = logging.getLogger("life_sandbox.telegram")

router = APIRouter(prefix="/api/v1/integrations/telegram", tags=["telegram"])


def telegram_is_configured() -> bool:
    """Return True if a Telegram bot token is present."""
    settings = get_settings()
    return bool(getattr(settings, "telegram_bot_token", None))


def get_allowed_chat_ids() -> set[str]:
    """Retrieve the set of Telegram chat/user IDs permitted to converse with the agent."""
    settings = get_settings()
    allowed: set[str] = set()
    raw = getattr(settings, "telegram_allowed_chat_ids", None)
    if raw:
        for item in str(raw).split(","):
            clean = item.strip()
            if clean:
                allowed.add(clean)
    chat_id = getattr(settings, "telegram_chat_id", None)
    if chat_id:
        allowed.add(str(chat_id).strip())
    return allowed


def is_chat_allowed(chat_id: str | int | None) -> bool:
    """Check whether a given Telegram chat ID is authorized."""
    if not chat_id:
        return False
    allowed = get_allowed_chat_ids()
    if not allowed:
        # Deny by default if no allowed chat IDs or default chat ID are configured
        return False
    return str(chat_id).strip() in allowed


def chunk_message(text: str, max_length: int = 4000) -> list[str]:
    """Split long messages into chunks that respect Telegram's 4096-character limit."""
    clean = (text or "").strip()
    if len(clean) <= max_length:
        return [clean]
    chunks: list[str] = []
    lines = clean.split("\n")
    current: list[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_length:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            if len(line) > max_length:
                for i in range(0, len(line), max_length):
                    chunks.append(line[i : i + max_length])
            else:
                current.append(line)
                current_len = len(line)
        else:
            current.append(line)
            current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def sanitize_telegram_response(text: str) -> str:
    """Strip reasoning monologues and convert any OpenUI DSL to clean markdown."""
    clean = (text or "").strip()
    if not clean:
        return clean

    has_openui = bool(
        re.search(r"\broot\s*=\s*Card\b", clean)
        or re.search(r"\bCardHeader\s*\(", clean)
        or re.search(r"\bSnippetCardBlock\s*\(", clean)
        or re.search(r"\bTextContent\s*\(", clean)
    )

    if has_openui:
        header_title = ""
        header_subtitle = ""
        ch_m = re.search(r'CardHeader\(\s*"([^"]+)"(?:,\s*"([^"]+)")?\)', clean)
        if ch_m:
            header_title = ch_m.group(1).strip()
            header_subtitle = (ch_m.group(2) or "").strip()

        kpi_lines = []
        for icon_m in re.finditer(r'IconText\([^,]+,[^,]+,[^,]+,\s*"([^"]+)",\s*"([^"]+)"', clean):
            label, val = icon_m.group(1), icon_m.group(2)
            kpi_lines.append(f"• **{label}:** {val}")

        text_contents = []
        for tc_m in re.finditer(r'TextContent\(\s*"((?:[^"\\]|\\.)*)"', clean):
            raw_text = tc_m.group(1)
            unescaped = raw_text.replace('\\"', '"').replace("\\n", "\n")
            text_contents.append(unescaped.strip())

        inline_headers = []
        for ih_m in re.finditer(r'InlineHeader\(\s*"([^"]+)"(?:,\s*"([^"]+)")?\)', clean):
            ih_title = ih_m.group(1)
            ih_desc = ih_m.group(2) or ""
            hdr_str = f"**{ih_title}**"
            if ih_desc:
                hdr_str += f": {ih_desc}"
            inline_headers.append(hdr_str)

        parts = []
        if header_title:
            title_block = f"📊 **{header_title}**"
            if header_subtitle:
                title_block += f"\n*{header_subtitle}*"
            parts.append(title_block)

        if kpi_lines:
            parts.append("**Key Comparison Metrics:**\n" + "\n".join(kpi_lines))

        if text_contents:
            parts.append("\n\n".join(text_contents))

        if inline_headers:
            parts.append("\n".join(inline_headers))

        if parts:
            clean = "\n\n".join(parts)

    lines = clean.split("\n")
    start_idx = 0
    while start_idx < len(lines):
        line = lines[start_idx].strip()
        lower = line.lower()
        if (
            lower.startswith("lifesandbox:")
            or lower.startswith("let me first check")
            or lower.startswith("actually, let me just build")
            or lower.startswith("actually, let me")
            or lower.startswith("let me structure this")
            or lower.startswith("let me structure a comparison")
            or lower.startswith("let me think")
            or lower.startswith("i will structure")
        ):
            start_idx += 1
        elif not line and start_idx > 0:
            start_idx += 1
        else:
            break

    if start_idx > 0 and start_idx < len(lines):
        clean = "\n".join(lines[start_idx:]).strip()

    return clean


def format_markdown_for_telegram(text: str) -> str:
    """Format markdown text into clean Telegram HTML."""
    sanitized = sanitize_telegram_response(text)
    if not sanitized:
        return ""

    if re.search(r"<(?:b|i|code|pre|a)\b", sanitized):
        return sanitized

    res = html.escape(sanitized)
    res = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", res, flags=re.MULTILINE)
    res = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", res)
    res = re.sub(r"__(.+?)__", r"<b>\1</b>", res)
    res = re.sub(r"`([^`]+)`", r"<code>\1</code>", res)
    res = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', res)

    return res


def extract_oauth_code_and_state(text: str) -> tuple[str | None, str | None]:
    """Extract code and state parameters from a URL or callback command string."""
    clean = text.strip()
    if clean.lower().startswith("/callback"):
        clean = clean[len("/callback"):].strip()
    clean = clean.strip("<>\"'")

    if "code=" in clean and "state=" in clean:
        parsed = urlparse(clean)
        qs = parsed.query if parsed.query else clean
        params = parse_qs(qs)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        if code and state:
            return code, state

        code_match = re.search(r"(?:[?&]|\b)code=([^&\s]+)", clean)
        state_match = re.search(r"(?:[?&]|\b)state=([^&\s]+)", clean)
        if code_match and state_match:
            return unquote(code_match.group(1)), unquote(state_match.group(1))

    return None, None


async def send_telegram_action(chat_id: str | int, action: str = "typing") -> bool:
    """Send a chat action indicator (such as 'typing') to Telegram."""
    settings = get_settings()
    token = getattr(settings, "telegram_bot_token", None)
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/sendChatAction"
    payload = {"chat_id": str(chat_id), "action": action}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False


async def _keep_typing(chat_id: str | int, stop_event: asyncio.Event) -> None:
    """Background task to keep the 'typing' status alive while agent is thinking."""
    while not stop_event.is_set():
        try:
            await send_telegram_action(chat_id, "typing")
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except TimeoutError:
            pass


async def send_telegram_message(
    message: str,
    chat_id: str | int | None = None,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    """Send a message to a user or channel on Telegram, splitting into chunks if necessary."""
    settings = get_settings()
    token = getattr(settings, "telegram_bot_token", None)
    if not token:
        raise HTTPException(
            503,
            detail={
                "code": "telegram_unconfigured",
                "message": "TELEGRAM_BOT_TOKEN must be configured in .env to use Telegram.",
            },
        )

    target_chat_id = chat_id or getattr(settings, "telegram_chat_id", None)
    if not target_chat_id:
        raise HTTPException(
            400,
            detail={
                "code": "telegram_chat_id_missing",
                "message": (
                    "No Telegram chat ID provided. Provide chat_id or set TELEGRAM_CHAT_ID in .env."
                ),
            },
        )

    clean_message = (message or "").strip()
    if not clean_message:
        raise HTTPException(
            422,
            detail={"code": "empty_message", "message": "Telegram message text cannot be empty."},
        )

    chunks = chunk_message(clean_message, max_length=4000)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    last_result: dict[str, Any] = {}
    max_retries = 3

    for chunk in chunks:
        payload: dict[str, Any] = {
            "chat_id": str(target_chat_id),
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        sent = False
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(20.0, connect=10.0)
                ) as client:
                    response = await client.post(url, json=payload)
                    if response.status_code == 400 and payload.get("parse_mode"):
                        # If HTML/formatting fails, fall back to plain text
                        payload.pop("parse_mode", None)
                        response = await client.post(url, json=payload)

                    response.raise_for_status()
                    data = response.json()
                    if not data.get("ok"):
                        raise HTTPException(
                            502,
                            detail={
                                "code": "telegram_error",
                                "message": data.get(
                                    "description", "Telegram API returned an error."
                                ),
                            },
                        )
                    res_data = data.get("result", {})
                    last_result = {
                        "status": "sent",
                        "message_id": res_data.get("message_id"),
                        "chat_id": str(target_chat_id),
                        "date": res_data.get("date"),
                    }
                    sent = True
                    break
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    502,
                    detail={
                        "code": "telegram_http_error",
                        "message": f"Telegram API failed with status {exc.response.status_code}.",
                    },
                ) from exc
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < max_retries:
                    logger.warning(
                        "Transient network error sending to Telegram (attempt %s/%s): %s. "
                        "Retrying...",
                        attempt,
                        max_retries,
                        exc,
                    )
                    await asyncio.sleep(0.8 * attempt)
                else:
                    logger.error(
                        "Failed connecting to Telegram servers after %s attempts: %s",
                        max_retries,
                        exc,
                    )
            except HTTPException:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    await asyncio.sleep(0.8 * attempt)

        if not sent:
            raise HTTPException(
                502,
                detail={
                    "code": "telegram_network_error",
                    "message": f"Could not connect to Telegram servers: {last_error}",
                },
            )

    return last_result


async def get_telegram_bot_info() -> dict[str, Any]:
    """Retrieve metadata about the configured Telegram bot."""
    settings = get_settings()
    token = getattr(settings, "telegram_bot_token", None)
    if not token:
        return {"configured": False}

    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                result = data.get("result", {})
                return {
                    "configured": True,
                    "id": result.get("id"),
                    "username": result.get("username"),
                    "first_name": result.get("first_name"),
                }
    except Exception:
        pass
    return {"configured": True, "status": "unreachable"}


async def set_telegram_webhook(webhook_url: str, secret_token: str | None = None) -> dict[str, Any]:
    """Set the Telegram bot webhook URL."""
    settings = get_settings()
    token = getattr(settings, "telegram_bot_token", None)
    if not token:
        raise HTTPException(status_code=503, detail="Telegram bot token not configured")

    url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload: dict[str, Any] = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        return resp.json()


async def delete_telegram_webhook(drop_pending_updates: bool = False) -> dict[str, Any]:
    """Delete any active Telegram webhook (required before using getUpdates polling)."""
    settings = get_settings()
    token = getattr(settings, "telegram_bot_token", None)
    if not token:
        return {"configured": False}

    url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json={"drop_pending_updates": drop_pending_updates})
            return resp.json()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def get_telegram_webhook_info() -> dict[str, Any]:
    """Fetch current webhook information from Telegram."""
    settings = get_settings()
    token = getattr(settings, "telegram_bot_token", None)
    if not token:
        return {"configured": False}

    url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            return resp.json()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def process_telegram_update(
    update: dict[str, Any],
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Process an incoming update from Telegram, run through the agent, and reply."""
    if db is None:
        async with SessionLocal() as session:
            return await process_telegram_update(update, db=session)

    msg = update.get("message") or update.get("edited_message")
    if not isinstance(msg, dict):
        return {"status": "ignored", "reason": "no_message"}

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return {"status": "ignored", "reason": "no_chat_id"}

    settings = get_settings()
    user_id = getattr(settings, "telegram_default_user_id", "local-user")

    # Authorization Check
    if not is_chat_allowed(chat_id):
        logger.warning("Unauthorized access attempt to Telegram bot from chat_id=%s", chat_id)
        denied_msg = (
            "⛔ <b>Access Denied</b>\n\n"
            f"Your Telegram Chat ID is: <code>{chat_id}</code>\n\n"
            "This Life Sandbox agent is configured for private use. To grant access, "
            "add this Chat ID to <code>TELEGRAM_ALLOWED_CHAT_IDS</code> or "
            "<code>TELEGRAM_CHAT_ID</code> in your <code>.env</code> file."
        )
        try:
            await send_telegram_message(message=denied_msg, chat_id=chat_id)
        except Exception:
            pass
        return {"status": "unauthorized", "chat_id": str(chat_id)}

    text = (msg.get("text") or msg.get("caption") or "").strip()
    if not text:
        unsupported_msg = (
            "I received your file or media, but currently I can only process text "
            "messages directly. Please describe what you would like to do!"
        )
        await send_telegram_message(message=unsupported_msg, chat_id=chat_id)
        return {"status": "ignored", "reason": "empty_or_non_text"}

    # Special Command Handlers
    lowered = text.lower()
    if lowered in {"/start", "/help"}:
        welcome_text = (
            "👋 <b>Welcome to Life Sandbox!</b>\n\n"
            "I am your personal AI assistant. You can chat with me naturally from Telegram to:\n"
            "• 📅 <b>Calendar:</b> View schedules, find free slots, create, reschedule & delete events\n"
            "• ✉️ <b>Gmail:</b> Search, read, compose & send emails, reply to threads, archive, star & trash\n"
            "• 📁 <b>Google Drive:</b> Search, read, create Docs/Sheets/files, edit content, create folders & delete\n"
            "• 🌐 <b>Research:</b> Perform live web research & verification\n"
            "• ⚡ <b>Productivity:</b> Track decisions, projects, tasks, and reminders\n\n"
            "<b>Management Commands:</b>\n"
            "• <code>/connect_google</code> — Link your Google account\n"
            "• <code>/google_status</code> — Check connected Google account and capabilities\n"
            "• <code>/approvals</code> or <code>/pending</code> — View actions awaiting your approval\n"
            "• <code>/approve &lt;id&gt;</code> — Approve and execute a pending action\n"
            "• <code>/reject &lt;id&gt;</code> — Reject a pending action\n"
            "• <code>/new</code> or <code>/reset</code> — Start a fresh conversation thread\n"
            "• <code>/status</code> — View agent connection status\n"
            "• <code>/help</code> — Show this guide\n\n"
            "What can I help you with today?"
        )
        await send_telegram_message(message=welcome_text, chat_id=chat_id)
        return {"status": "command_handled", "command": lowered}

    if lowered in {"/connect_google", "/auth_google", "/auth"}:
        config = get_settings()
        if not all((config.google_oauth_client_id, config.google_oauth_client_secret, config.google_oauth_callback_url)):
            missing_msg = (
                "⚠️ <b>Google OAuth Not Configured</b>\n\n"
                "To enable Google integrations (Gmail, Calendar, Drive), ensure these are set in your <code>.env</code> file:\n"
                "• <code>GOOGLE_OAUTH_CLIENT_ID</code>\n"
                "• <code>GOOGLE_OAUTH_CLIENT_SECRET</code>\n"
                "• <code>GOOGLE_OAUTH_CALLBACK_URL</code>\n"
                "• <code>GOOGLE_TOKEN_ENCRYPTION_KEY</code>"
            )
            await send_telegram_message(message=missing_msg, chat_id=chat_id)
            return {"status": "command_handled", "command": lowered}

        try:
            auth_url = await create_google_authorization_url(user_id=user_id, db=db)
            connect_msg = (
                "🔗 <b>Connect Your Google Account</b>\n\n"
                "Click the link below to grant Life Sandbox access to your Gmail, Calendar, and Drive:\n\n"
                f"👉 <a href=\"{auth_url}\"><b>Authorize Google Account</b></a>\n\n"
                "<i>This link is valid for 10 minutes. Once authorized, you can perform all your operations right here from Telegram!</i>\n\n"
                "💡 <b>Tip if running locally:</b>\n"
                "If your browser shows <i>\"Site can't be reached\"</i> after you approve permissions (because <code>localhost:8000</code> is running on your computer and not reachable from your phone), simply <b>copy the full URL from your browser's address bar and paste it directly into this chat</b>! I will finish connecting your account automatically."
            )
            await send_telegram_message(message=connect_msg, chat_id=chat_id)
            return {"status": "command_handled", "command": lowered}
        except Exception as exc:
            err_msg = f"⚠️ Could not generate authorization link: {html.escape(str(exc))}"
            await send_telegram_message(message=err_msg, chat_id=chat_id)
            return {"status": "error", "error": str(exc)}

    # Google OAuth Callback via Telegram (pasted redirect URL or /callback)
    oauth_code, oauth_state = extract_oauth_code_and_state(text)
    if oauth_code and oauth_state:
        try:
            result = await complete_google_callback(code=oauth_code, state=oauth_state, db=db)
            account_email = result.get("account_email") or "Connected Account"
            token_scopes = result.get("token_scopes", [])
            success_msg = (
                "🎉 <b>Google Account Connected Successfully!</b>\n\n"
                f"• <b>Account:</b> <code>{html.escape(account_email)}</code>\n"
                f"• <b>Capabilities:</b> {len(token_scopes)} permissions active\n\n"
                "You can now manage your <b>Calendar, Gmail, and Google Drive</b> directly from Telegram!\n\n"
                "<b>Try asking me:</b>\n"
                "• <i>\"What's on my schedule today?\"</i>\n"
                "• <i>\"Check my latest unread emails\"</i>\n"
                "• <i>\"List files in my Google Drive\"</i>"
            )
            await send_telegram_message(message=success_msg, chat_id=chat_id)
            return {"status": "google_connected", "account_email": account_email}
        except HTTPException as exc:
            detail = exc.detail
            msg = detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
            err_msg = f"⚠️ <b>Google Connection Failed:</b> {html.escape(msg)}\n\nPlease run <code>/connect_google</code> to get a fresh link and try again."
            await send_telegram_message(message=err_msg, chat_id=chat_id)
            return {"status": "error", "error": msg}
        except Exception as exc:
            err_msg = f"⚠️ <b>Google Connection Error:</b> {html.escape(str(exc))}\n\nPlease run <code>/connect_google</code> to try again."
            await send_telegram_message(message=err_msg, chat_id=chat_id)
            return {"status": "error", "error": str(exc)}

    if lowered == "/callback":
        help_cb_msg = (
            "ℹ️ <b>How to Complete Connection:</b>\n\n"
            "If your browser showed <i>\"Site can't be reached\"</i> after signing into Google, "
            "copy the full URL from your browser's address bar and paste it here directly, or type:\n"
            "<code>/callback &lt;paste URL here&gt;</code>"
        )
        await send_telegram_message(message=help_cb_msg, chat_id=chat_id)
        return {"status": "command_handled", "command": "/callback"}

    if lowered == "/google_status":
        rows = (
            await db.scalars(
                select(IntegrationConnectionRow).where(
                    IntegrationConnectionRow.user_id == user_id,
                    IntegrationConnectionRow.provider == "google",
                )
            )
        ).all()
        if not rows:
            not_conn_msg = (
                "ℹ️ <b>Google Status: Not Connected</b>\n\n"
                "You haven't connected a Google account yet.\n"
                "Send <code>/connect_google</code> to link your account and unlock Gmail, Calendar, and Drive operations!"
            )
            await send_telegram_message(message=not_conn_msg, chat_id=chat_id)
            return {"status": "command_handled", "command": "/google_status"}

        status_lines = ["📊 <b>Google Connections:</b>\n"]
        for row in rows:
            scopes = json.loads(row.scopes)
            status_lines.append(f"• <b>Account:</b> {row.account_email or 'Connected'}")
            status_lines.append(f"  <b>Status:</b> <code>{row.status}</code>")
            status_lines.append(f"  <b>Authorized Scopes:</b> {len(scopes)} granted")
        await send_telegram_message(message="\n".join(status_lines), chat_id=chat_id)
        return {"status": "command_handled", "command": "/google_status"}

    if lowered in {"/approvals", "/pending"}:
        stmt = (
            select(ApprovalRow)
            .where(
                ApprovalRow.user_id == user_id,
                ApprovalRow.status == "pending",
            )
            .order_by(ApprovalRow.created_at.desc())
            .limit(10)
        )
        pending_rows = (await db.scalars(stmt)).all()
        if not pending_rows:
            await send_telegram_message(
                message="✅ <b>No pending approvals.</b> Everything is clear!",
                chat_id=chat_id,
            )
            return {"status": "command_handled", "command": lowered}

        lines = ["⏳ <b>Pending Actions Awaiting Approval:</b>\n"]
        for p in pending_rows:
            lines.append(f"• <b>Action:</b> <code>{html.escape(p.action)}</code>")
            lines.append(f"  <b>Details:</b> {html.escape(p.description or 'No description')}")
            lines.append(f"  <b>ID:</b> <code>{p.id}</code>")
            lines.append(f"  👉 To approve: <code>/approve {p.id}</code>\n")
        await send_telegram_message(message="\n".join(lines), chat_id=chat_id)
        return {"status": "command_handled", "command": lowered}

    if lowered.startswith("/approve"):
        parts = text.strip().split()
        if len(parts) < 2:
            await send_telegram_message(
                message="ℹ️ Please provide the approval ID: <code>/approve &lt;approval_id&gt;</code>",
                chat_id=chat_id,
            )
            return {"status": "command_handled", "command": "/approve"}
        approval_id = parts[1].strip()
        try:
            from app.api.workflow import execute_approval_action

            result = await execute_approval_action(
                db=db,
                user_id=user_id,
                approval_id=approval_id,
                correlation_id=f"telegram-{uuid4().hex[:8]}",
                allow_pending=True,
            )
            resource_ref = result.get("resource_id") or result.get("message_id") or ""
            res_type = result.get("resource_type") or ""
            success_msg = (
                f"✅ <b>Action Approved and Executed!</b>\n\n"
                f"• <b>Status:</b> <code>{result.get('status', 'executed')}</code>\n"
                f"• <b>Resource:</b> <code>{res_type} {resource_ref}</code>".strip()
            )
            await send_telegram_message(message=success_msg, chat_id=chat_id)
            return {"status": "approval_executed", "result": result}
        except Exception as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            err_msg = f"⚠️ <b>Approval Failed:</b> {html.escape(str(detail))}"
            await send_telegram_message(message=err_msg, chat_id=chat_id)
            return {"status": "error", "error": str(exc)}

    if lowered.startswith("/reject"):
        parts = text.strip().split()
        if len(parts) < 2:
            await send_telegram_message(
                message="ℹ️ Please provide the approval ID: <code>/reject &lt;approval_id&gt;</code>",
                chat_id=chat_id,
            )
            return {"status": "command_handled", "command": "/reject"}
        approval_id = parts[1].strip()
        approval = await db.scalar(
            select(ApprovalRow).where(
                ApprovalRow.id == approval_id, ApprovalRow.user_id == user_id
            )
        )
        if approval is None:
            await send_telegram_message(message="⚠️ Approval not found.", chat_id=chat_id)
            return {"status": "not_found"}
        if approval.status != "pending":
            await send_telegram_message(
                message=f"ℹ️ Approval is already <code>{approval.status}</code>.", chat_id=chat_id
            )
            return {"status": "already_resolved"}
        approval.status = "rejected"
        approval.decided_at = datetime.now(UTC)
        db.add(
            AuditRow(
                user_id=user_id,
                action="approval.reject",
                resource_id=approval.id,
                outcome="rejected",
                correlation_id=f"telegram-{uuid4().hex[:8]}",
            )
        )
        await db.commit()
        await send_telegram_message(message="❌ <b>Action rejected.</b>", chat_id=chat_id)
        return {"status": "rejected", "approval_id": approval_id}

    if lowered == "/status":
        bot_info = await get_telegram_bot_info()
        status_text = (
            "🤖 <b>Life Sandbox Status</b>\n\n"
            f"• <b>Bot:</b> @{bot_info.get('username', 'configured')}\n"
            f"• <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"• <b>Bound User:</b> <code>{user_id}</code>\n"
            f"• <b>LLM Provider:</b> <code>{settings.llm_provider}</code>\n"
            f"• <b>State:</b> Active & Connected"
        )
        await send_telegram_message(message=status_text, chat_id=chat_id)
        return {"status": "command_handled", "command": "/status"}

    if lowered in {"/new", "/reset"}:
        new_conv = ConversationRow(
            id=str(uuid4()),
            user_id=user_id,
            title=f"Telegram ({chat_id}) - {datetime.now(UTC).strftime('%b %d, %H:%M')}",
        )
        db.add(new_conv)
        await db.commit()
        await send_telegram_message(
            message="🔄 <b>Fresh conversation started.</b> How can I help you?",
            chat_id=chat_id,
        )
        return {"status": "conversation_reset", "conversation_id": new_conv.id}

    # Locate ongoing conversation or create a new one for this Telegram chat
    conv_stmt = (
        select(ConversationRow)
        .where(
            ConversationRow.user_id == user_id,
            ConversationRow.title.like(f"Telegram ({chat_id})%"),
        )
        .order_by(ConversationRow.updated_at.desc())
        .limit(1)
    )
    existing_conv = (await db.scalars(conv_stmt)).first()
    if existing_conv is None:
        conversation_id = str(uuid4())
        new_conv = ConversationRow(
            id=conversation_id,
            user_id=user_id,
            title=f"Telegram ({chat_id}) - {datetime.now(UTC).strftime('%b %d, %H:%M')}",
        )
        db.add(new_conv)
        await db.commit()
    else:
        conversation_id = existing_conv.id

    # Display typing indicator while agent processes
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(chat_id, stop_typing))

    from app.services.chat import run_chat

    try:
        chat_result = await run_chat(
            db=db,
            user_id=user_id,
            message=text,
            conversation_id=conversation_id,
            channel="telegram",
        )
        reply = (
            chat_result.get("reply", "No response generated.")
            if chat_result
            else "No response generated."
        )
        reply = format_markdown_for_telegram(reply)
    except Exception as exc:
        logger.exception("Failed to run chat turn for Telegram message: %s", exc)
        reply = f"⚠️ I encountered an error while processing your request: {html.escape(str(exc))}"
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except (asyncio.CancelledError, Exception):
            pass

    # Send agent response back to user
    try:
        await send_telegram_message(message=reply, chat_id=chat_id)
    except Exception as send_exc:
        logger.warning(
            "Initial send_telegram_message failed: %s. Retrying with plain text...",
            send_exc,
        )
        await asyncio.sleep(1.0)
        await send_telegram_message(message=reply, chat_id=chat_id, parse_mode="")
    return {
        "status": "replied",
        "chat_id": str(chat_id),
        "conversation_id": conversation_id,
    }


async def run_telegram_polling(stop_event: asyncio.Event | None = None) -> None:
    """Run a long-polling loop to consume Telegram updates without needing a webhook."""
    settings = get_settings()
    token = getattr(settings, "telegram_bot_token", None)
    if not token:
        logger.info("Telegram polling worker not started: TELEGRAM_BOT_TOKEN not configured.")
        return

    stop_event = stop_event or asyncio.Event()
    logger.info("Starting Telegram long-polling worker...")

    # Clear active webhook if present so getUpdates works cleanly
    try:
        await delete_telegram_webhook(drop_pending_updates=False)
    except Exception as exc:
        logger.debug("Webhook deletion attempt during polling startup: %s", exc)

    offset = 0
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    while not stop_event.is_set():
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params: dict[str, Any] = {"offset": offset, "timeout": 20}
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    updates = data.get("result", [])
                    for upd in updates:
                        upd_id = upd.get("update_id")
                        if upd_id is not None:
                            offset = max(offset, upd_id + 1)
                        try:
                            async with SessionLocal() as db:
                                await process_telegram_update(upd, db=db)
                        except Exception as upd_exc:
                            logger.exception(
                                "Error processing Telegram update %s: %s", upd_id, upd_exc
                            )
                elif response.status_code == 409:
                    # Conflict: Webhook still active
                    logger.warning("Telegram polling 409 conflict. Retrying deleteWebhook...")
                    await delete_telegram_webhook(drop_pending_updates=False)
                    await asyncio.sleep(2.0)
                else:
                    logger.warning(
                        "Telegram getUpdates returned status %s: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    await asyncio.sleep(3.0)
        except asyncio.CancelledError:
            break
        except httpx.RequestError as req_err:
            logger.debug("Telegram polling network timeout/error: %s", req_err)
            await asyncio.sleep(2.0)
        except Exception as exc:
            logger.exception("Unexpected error in Telegram polling loop: %s", exc)
            await asyncio.sleep(3.0)

    logger.info("Telegram long-polling worker stopped.")


# API Endpoints for Webhook & Diagnostics


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session),
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> dict[str, Any]:
    """Endpoint receiving incoming updates from Telegram webhook."""
    settings = get_settings()
    configured_secret = getattr(settings, "telegram_webhook_secret", None)
    if configured_secret and x_telegram_bot_api_secret_token != configured_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON body") from exc

    result = await process_telegram_update(body, db=db)
    return {"ok": True, "result": result}


@router.post("/set-webhook")
async def api_set_webhook(
    payload: dict[str, Any],
    _: Principal = Depends(current_principal),
) -> dict[str, Any]:
    """Set the Telegram bot webhook to a specified HTTPS URL."""
    url = payload.get("webhook_url")
    if not url:
        raise HTTPException(status_code=400, detail="webhook_url is required")
    secret = payload.get("secret_token")
    return await set_telegram_webhook(url, secret)


@router.post("/delete-webhook")
async def api_delete_webhook(
    _: Principal = Depends(current_principal),
) -> dict[str, Any]:
    """Delete the active Telegram bot webhook."""
    return await delete_telegram_webhook()


@router.get("/status")
async def telegram_integration_status(
    _: Principal = Depends(current_principal),
) -> dict[str, Any]:
    """Inspect current Telegram integration and connection status."""
    settings = get_settings()
    bot_info = await get_telegram_bot_info()
    webhook_info = await get_telegram_webhook_info()
    return {
        "configured": telegram_is_configured(),
        "bot": bot_info,
        "webhook": webhook_info.get("result", {}),
        "polling_enabled": getattr(settings, "telegram_polling_enabled", True),
        "allowed_chat_ids": list(get_allowed_chat_ids()),
        "default_user_id": getattr(settings, "telegram_default_user_id", "local-user"),
    }
