import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.google import decrypt_credentials, encrypt_credentials
from app.persistence.models import IntegrationConnectionRow


async def _connection(
    db: AsyncSession, user_id: str, scope: str, connection_id: str | None = None
) -> tuple[IntegrationConnectionRow, str]:
    query = select(IntegrationConnectionRow).where(
        IntegrationConnectionRow.user_id == user_id,
        IntegrationConnectionRow.provider == "google",
        IntegrationConnectionRow.status == "connected",
    )
    if connection_id:
        query = query.where(IntegrationConnectionRow.id == connection_id)
    rows = (await db.scalars(query)).all()
    for row in rows:
        if scope in json.loads(row.scopes):
            credentials = decrypt_credentials(row.encrypted_credentials)
            token = credentials.get("access_token")
            if not token:
                continue
            expires = row.expires_at
            if expires and expires.replace(tzinfo=UTC) <= datetime.now(UTC) + timedelta(minutes=1):
                refresh = credentials.get("refresh_token")
                if not refresh:
                    row.status = "reauthorization_required"
                    await db.commit()
                    raise HTTPException(
                        409,
                        detail={
                            "code": "google_reconnect_required",
                            "message": "Google access expired. Reconnect the account.",
                        },
                    )
                config = get_settings()
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        response = await client.post(
                            "https://oauth2.googleapis.com/token",
                            data={
                                "client_id": config.google_oauth_client_id,
                                "client_secret": config.google_oauth_client_secret,
                                "refresh_token": refresh,
                                "grant_type": "refresh_token",
                            },
                        )
                        response.raise_for_status()
                        payload = response.json()
                    credentials["access_token"] = payload["access_token"]
                    row.encrypted_credentials = encrypt_credentials(credentials)
                    row.expires_at = datetime.now(UTC) + timedelta(
                        seconds=int(payload.get("expires_in", 3600))
                    )
                    await db.commit()
                    token = credentials["access_token"]
                except (httpx.HTTPError, KeyError, ValueError) as exc:
                    row.status = "reauthorization_required"
                    await db.commit()
                    raise HTTPException(
                        409,
                        detail={
                            "code": "google_refresh_failed",
                            "message": "Google authorization expired or was revoked. Reconnect.",
                        },
                    ) from exc
            return row, token
    raise HTTPException(
        409,
        detail={
            "code": "google_capability_unavailable",
            "message": "Connect Google and grant the requested capability first.",
        },
    )


async def _request(
    db: AsyncSession,
    user_id: str,
    scope: str,
    method: str,
    url: str,
    connection_id: str | None = None,
    **kwargs,
):
    row, token = await _connection(db, user_id, scope, connection_id)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(
                method, url, headers={"Authorization": f"Bearer {token}"}, **kwargs
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            row.status = "reauthorization_required"
            await db.commit()
            raise HTTPException(
                409,
                detail={
                    "code": "google_reconnect_required",
                    "message": "Google rejected the connection. Reconnect the account.",
                },
            ) from exc
        raise HTTPException(
            502,
            detail={
                "code": "google_provider_error",
                "message": "Google did not complete the requested operation.",
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            502,
            detail={
                "code": "google_provider_unavailable",
                "message": "Google could not be reached; the operation was not confirmed.",
            },
        ) from exc


def _event(event: dict, calendar_id: str):
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "calendar_id": calendar_id,
        "title": event.get("summary", "(untitled)"),
        "start": start.get("dateTime", start.get("date")),
        "end": end.get("dateTime", end.get("date")),
        "timezone": start.get("timeZone") or end.get("timeZone"),
        "all_day": "date" in start,
        "location": event.get("location"),
    }


async def list_events(
    db: AsyncSession,
    user_id: str,
    start: datetime,
    end: datetime,
    timezone: str,
    calendar_id: str = "primary",
    limit: int = 50,
):
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or end <= start
        or end - start > timedelta(days=31)
        or not 1 <= limit <= 100
    ):
        raise ValueError(
            "Use an aware time range of at most 31 days and a result limit from 1 to 100"
        )
    if calendar_id != "primary" and not all(
        character.isalnum() or character in "_.@+-" for character in calendar_id
    ):
        raise ValueError("Invalid calendar ID")
    ZoneInfo(timezone)
    body = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/calendar.readonly",
        "GET",
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        params={
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": timezone,
            "maxResults": limit,
            "singleEvents": "true",
            "orderBy": "startTime",
        },
    )
    return {
        "items": [_event(item, calendar_id) for item in body.get("items", [])],
        "connection": "google",
    }


async def find_free_time(
    db: AsyncSession,
    user_id: str,
    start: datetime,
    end: datetime,
    timezone: str,
    duration_minutes: int,
    working_start: int = 9,
    working_end: int = 17,
):
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or end <= start
        or end - start > timedelta(days=14)
        or not 1 <= duration_minutes <= 480
        or not 0 <= working_start < working_end <= 24
    ):
        raise ValueError("Invalid availability window, duration, or work hours")
    ZoneInfo(timezone)
    body = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/calendar.readonly",
        "POST",
        "https://www.googleapis.com/calendar/v3/freeBusy",
        json={
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": timezone,
            "items": [{"id": "primary"}],
        },
    )
    busy = body.get("calendars", {}).get("primary", {}).get("busy", [])
    zone = ZoneInfo(timezone)
    candidates = []
    day = start.astimezone(zone).date()
    last = end.astimezone(zone).date()
    while day <= last:
        cursor = datetime(day.year, day.month, day.day, working_start, tzinfo=zone)
        finish = datetime(day.year, day.month, day.day, working_end, tzinfo=zone)
        cursor = max(cursor, start.astimezone(zone))
        finish = min(finish, end.astimezone(zone))
        conflicts = sorted(
            (
                datetime.fromisoformat(item["start"].replace("Z", "+00:00")).astimezone(zone),
                datetime.fromisoformat(item["end"].replace("Z", "+00:00")).astimezone(zone),
            )
            for item in busy
        )
        for busy_start, busy_end in conflicts:
            if busy_end <= cursor or busy_start >= finish:
                continue
            while cursor + timedelta(minutes=duration_minutes) <= min(busy_start, finish):
                candidates.append(
                    {
                        "start": cursor.isoformat(),
                        "end": (cursor + timedelta(minutes=duration_minutes)).isoformat(),
                    }
                )
                cursor += timedelta(minutes=duration_minutes)
            cursor = max(cursor, busy_end)
        while cursor + timedelta(minutes=duration_minutes) <= finish:
            candidates.append(
                {
                    "start": cursor.isoformat(),
                    "end": (cursor + timedelta(minutes=duration_minutes)).isoformat(),
                }
            )
            cursor += timedelta(minutes=duration_minutes)
        day += timedelta(days=1)
    return {"slots": candidates[:20], "source": "Google Calendar freeBusy"}


async def search_messages(db: AsyncSession, user_id: str, query: str, limit: int = 10):
    try:
        return await asyncio.wait_for(_search_messages(db, user_id, query, limit), timeout=25)
    except TimeoutError as exc:
        raise HTTPException(
            504,
            detail={
                "code": "google_tool_timeout",
                "message": (
                    "Gmail search timed out before results were confirmed. "
                    "Narrow the query and retry."
                ),
            },
        ) from exc


async def _search_messages(db: AsyncSession, user_id: str, query: str, limit: int = 10):
    if not query.strip() or len(query) > 500 or not 1 <= limit <= 25:
        raise ValueError("Use a Gmail query up to 500 characters and limit 1 to 25")
    body = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/gmail.readonly",
        "GET",
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        params={"q": query, "maxResults": limit},
    )
    results = []
    for ref in body.get("messages", []):
        msg = await _request(
            db,
            user_id,
            "https://www.googleapis.com/auth/gmail.readonly",
            "GET",
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{ref['id']}",
            params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
        )
        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in msg.get("payload", {}).get("headers", [])
        }
        results.append(
            {
                "id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "from": headers.get("from"),
                "to": headers.get("to"),
                "subject": headers.get("subject"),
                "timestamp": headers.get("date"),
                "snippet": msg.get("snippet", "")[:500],
                "labels": msg.get("labelIds", []),
            }
        )
    return {"items": results, "connection": "google"}


def _decode_part(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if data:
        try:
            return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(
                "utf-8", errors="replace"
            )
        except (ValueError, UnicodeError):
            return ""
    return "\n".join(_decode_part(child) for child in part.get("parts", []))


async def get_thread(db: AsyncSession, user_id: str, thread_id: str, limit: int = 10):
    if (
        not thread_id
        or len(thread_id) > 200
        or "/" in thread_id
        or ".." in thread_id
        or not 1 <= limit <= 20
    ):
        raise ValueError("Invalid Gmail thread ID or message limit")
    body = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/gmail.readonly",
        "GET",
        f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}",
        params={"format": "full"},
    )
    messages = []
    for msg in body.get("messages", [])[:limit]:
        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in msg.get("payload", {}).get("headers", [])
        }
        messages.append(
            {
                "id": msg.get("id"),
                "timestamp": headers.get("date"),
                "from": headers.get("from"),
                "to": headers.get("to"),
                "subject": headers.get("subject"),
                "body": _decode_part(msg.get("payload", {}))[:6000],
            }
        )
    return {"id": body.get("id"), "messages": messages, "content_untrusted": True}


async def create_draft(
    db: AsyncSession,
    user_id: str,
    to: list[str],
    subject: str,
    body: str,
    thread_id: str | None = None,
    connection_id: str | None = None,
):
    if (
        not to
        or len(to) > 10
        or any("\n" in recipient or "\r" in recipient or "@" not in recipient for recipient in to)
        or "\n" in subject
        or "\r" in subject
        or len(subject) > 500
        or len(body) > 20000
    ):
        raise ValueError("Draft recipients, subject, or body are invalid")
    connection, _ = await _connection(
        db, user_id, "https://www.googleapis.com/auth/gmail.compose", connection_id
    )
    connection_id = connection.id
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    request_body = {
        "message": {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")}
    }
    if thread_id:
        request_body["message"]["threadId"] = thread_id
    draft = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/gmail.compose",
        "POST",
        "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
        connection_id=connection_id,
        json=request_body,
    )
    return {
        "draft_id": draft.get("id"),
        "message_id": draft.get("message", {}).get("id"),
        "thread_id": draft.get("message", {}).get("threadId"),
        "status": "draft_created",
        "connection_id": connection_id,
    }


async def read_draft(db: AsyncSession, user_id: str, connection_id: str, draft_id: str) -> dict:
    if not draft_id or len(draft_id) > 200 or "/" in draft_id or ".." in draft_id:
        raise ValueError("Invalid Gmail draft ID")
    body = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/gmail.compose",
        "GET",
        f"https://gmail.googleapis.com/gmail/v1/users/me/drafts/{draft_id}",
        connection_id=connection_id,
        params={"format": "full"},
    )
    message = body.get("message", {})
    headers = {
        item.get("name", "").lower(): item.get("value", "")
        for item in message.get("payload", {}).get("headers", [])
    }
    content = {
        "draft_id": body.get("id"),
        "message_id": message.get("id"),
        "thread_id": message.get("threadId"),
        "recipients": {
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "bcc": headers.get("bcc", ""),
        },
        "subject": headers.get("subject", ""),
        "body": _decode_part(message.get("payload", {}))[:20000],
        "connection_id": connection_id,
    }
    content["content_hash"] = hashlib.sha256(
        json.dumps(
            {
                key: content[key]
                for key in ("draft_id", "recipients", "subject", "body", "thread_id")
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return content


class GoogleActionUncertain(RuntimeError):
    """The request may have reached Google; it must not be blindly retried."""


async def send_draft(db: AsyncSession, user_id: str, connection_id: str, draft_id: str) -> dict:
    _, token = await _connection(
        db, user_id, "https://www.googleapis.com/auth/gmail.send", connection_id
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/drafts/send",
                headers={"Authorization": f"Bearer {token}"},
                json={"id": draft_id},
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise GoogleActionUncertain from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise GoogleActionUncertain from exc
        raise HTTPException(
            502,
            detail={
                "code": "google_send_rejected",
                "message": "Google rejected the approved draft send request.",
            },
        ) from exc
    if not result.get("id"):
        raise GoogleActionUncertain
    return {"message_id": result["id"], "thread_id": result.get("threadId"), "status": "sent"}
