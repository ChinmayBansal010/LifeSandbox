import html
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import get_settings


def telegram_is_configured() -> bool:
    settings = get_settings()
    return bool(settings.telegram_bot_token)


async def send_telegram_message(
    message: str,
    chat_id: str | int | None = None,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    """Send a message to a user or channel on Telegram."""
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        raise HTTPException(
            503,
            detail={
                "code": "telegram_unconfigured",
                "message": "TELEGRAM_BOT_TOKEN must be configured in .env to use Telegram.",
            },
        )

    target_chat_id = chat_id or settings.telegram_chat_id
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

    # Telegram message length limit is 4096 characters
    if len(clean_message) > 4000:
        clean_message = clean_message[:3997] + "..."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": str(target_chat_id),
        "text": clean_message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 400 and parse_mode:
                # If markdown/HTML parsing fails, retry without parse_mode
                payload.pop("parse_mode", None)
                response = await client.post(url, json=payload)

            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise HTTPException(
                    502,
                    detail={
                        "code": "telegram_error",
                        "message": data.get("description", "Telegram API returned an error."),
                    },
                )

            result = data.get("result", {})
            return {
                "status": "sent",
                "message_id": result.get("message_id"),
                "chat_id": str(target_chat_id),
                "date": result.get("date"),
            }
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            502,
            detail={
                "code": "telegram_http_error",
                "message": f"Telegram API failed with status {exc.response.status_code}.",
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            502,
            detail={
                "code": "telegram_network_error",
                "message": "Could not connect to Telegram servers.",
            },
        ) from exc


async def get_telegram_bot_info() -> dict[str, Any]:
    """Retrieve metadata about the configured Telegram bot."""
    settings = get_settings()
    token = settings.telegram_bot_token
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
