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

SCOPE_COMPATIBILITY: dict[str, set[str]] = {
    "https://www.googleapis.com/auth/calendar.readonly": {
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar",
    },
    "https://www.googleapis.com/auth/calendar.events": {
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar",
    },
    "https://www.googleapis.com/auth/calendar": {
        "https://www.googleapis.com/auth/calendar",
    },
    "https://www.googleapis.com/auth/gmail.readonly": {
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://mail.google.com/",
    },
    "https://www.googleapis.com/auth/gmail.compose": {
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://mail.google.com/",
    },
    "https://www.googleapis.com/auth/gmail.send": {
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://mail.google.com/",
    },
    "https://www.googleapis.com/auth/gmail.modify": {
        "https://www.googleapis.com/auth/gmail.modify",
        "https://mail.google.com/",
    },
    "https://www.googleapis.com/auth/drive.readonly": {
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    },
    "https://www.googleapis.com/auth/drive.file": {
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    },
    "https://www.googleapis.com/auth/drive": {
        "https://www.googleapis.com/auth/drive",
    },
}


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
    compatible_scopes = SCOPE_COMPATIBILITY.get(scope, {scope})
    for row in rows:
        granted = set(json.loads(row.scopes))
        if granted.intersection(compatible_scopes):
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
                    row.expires_at = datetime.now(UTC) + timedelta(seconds=int(payload.get("expires_in", 3600)))
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
    as_text: bool = False,
    **kwargs,
):
    row, token = await _connection(db, user_id, scope, connection_id)
    headers = {"Authorization": f"Bearer {token}"}
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            if as_text:
                return response.text
            if response.status_code == 204 or not response.text.strip():
                return {}
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
        raise ValueError("Use an aware time range of at most 31 days and a result limit from 1 to 100")
    if calendar_id != "primary" and not all(character.isalnum() or character in "_.@+-" for character in calendar_id):
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


def _format_datetime(dt_or_str: str | datetime, timezone_str: str = "UTC") -> str:
    if isinstance(dt_or_str, datetime):
        if dt_or_str.tzinfo is None:
            tz = ZoneInfo(timezone_str)
            dt_or_str = dt_or_str.replace(tzinfo=tz)
        return dt_or_str.isoformat()
    try:
        parsed = datetime.fromisoformat(dt_or_str)
        if parsed.tzinfo is None:
            tz = ZoneInfo(timezone_str)
            parsed = parsed.replace(tzinfo=tz)
        return parsed.isoformat()
    except Exception:
        return str(dt_or_str)


async def create_event(
    db: AsyncSession,
    user_id: str,
    summary: str,
    start: str | datetime,
    end: str | datetime,
    timezone: str = "UTC",
    description: str | None = None,
    location: str | None = None,
    attendees: list[str] | None = None,
    calendar_id: str = "primary",
    connection_id: str | None = None,
) -> dict:
    if not summary or len(summary) > 500:
        raise ValueError("Event summary is required and must be under 500 characters")
    ZoneInfo(timezone)
    start_iso = _format_datetime(start, timezone)
    end_iso = _format_datetime(end, timezone)

    payload: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    if description:
        payload["description"] = description[:5000]
    if location:
        payload["location"] = location[:500]
    if attendees:
        payload["attendees"] = [{"email": a.strip()} for a in attendees if "@" in a]

    body = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/calendar.events",
        "POST",
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        connection_id=connection_id,
        json=payload,
    )
    return {
        "status": "created",
        "id": body.get("id"),
        "calendar_id": calendar_id,
        "summary": body.get("summary", summary),
        "start": body.get("start", {}).get("dateTime", start_iso),
        "end": body.get("end", {}).get("dateTime", end_iso),
        "link": body.get("htmlLink"),
    }


async def update_event(
    db: AsyncSession,
    user_id: str,
    event_id: str,
    calendar_id: str = "primary",
    summary: str | None = None,
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    timezone: str = "UTC",
    description: str | None = None,
    location: str | None = None,
    attendees: list[str] | None = None,
    connection_id: str | None = None,
) -> dict:
    if not event_id or len(event_id) > 200:
        raise ValueError("Invalid event ID")
    ZoneInfo(timezone)
    payload: dict[str, Any] = {}
    if summary:
        payload["summary"] = summary[:500]
    if description is not None:
        payload["description"] = description[:5000]
    if location is not None:
        payload["location"] = location[:500]
    if start:
        payload["start"] = {"dateTime": _format_datetime(start, timezone), "timeZone": timezone}
    if end:
        payload["end"] = {"dateTime": _format_datetime(end, timezone), "timeZone": timezone}
    if attendees is not None:
        payload["attendees"] = [{"email": a.strip()} for a in attendees if "@" in a]

    body = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/calendar.events",
        "PATCH",
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
        connection_id=connection_id,
        json=payload,
    )
    return {
        "status": "updated",
        "id": body.get("id", event_id),
        "calendar_id": calendar_id,
        "summary": body.get("summary", summary),
        "start": body.get("start", {}).get("dateTime"),
        "end": body.get("end", {}).get("dateTime"),
        "link": body.get("htmlLink"),
    }


async def delete_event(
    db: AsyncSession,
    user_id: str,
    event_id: str,
    calendar_id: str = "primary",
    connection_id: str | None = None,
) -> dict:
    if not event_id or len(event_id) > 200:
        raise ValueError("Invalid event ID")
    await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/calendar.events",
        "DELETE",
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
        connection_id=connection_id,
    )
    return {"status": "deleted", "id": event_id, "calendar_id": calendar_id}


async def search_messages(db: AsyncSession, user_id: str, query: str, limit: int = 10):
    try:
        return await asyncio.wait_for(_search_messages(db, user_id, query, limit), timeout=25)
    except TimeoutError as exc:
        raise HTTPException(
            504,
            detail={
                "code": "google_tool_timeout",
                "message": ("Gmail search timed out before results were confirmed. Narrow the query and retry."),
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
        headers = {h.get("name", "").lower(): h.get("value", "") for h in msg.get("payload", {}).get("headers", [])}
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
            return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
        except (ValueError, UnicodeError):
            return ""
    return "\n".join(_decode_part(child) for child in part.get("parts", []))


async def get_thread(db: AsyncSession, user_id: str, thread_id: str, limit: int = 10):
    if not thread_id or len(thread_id) > 200 or "/" in thread_id or ".." in thread_id or not 1 <= limit <= 20:
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
        headers = {h.get("name", "").lower(): h.get("value", "") for h in msg.get("payload", {}).get("headers", [])}
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
    connection, _ = await _connection(db, user_id, "https://www.googleapis.com/auth/gmail.compose", connection_id)
    connection_id = connection.id
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    request_body = {"message": {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")}}
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
        item.get("name", "").lower(): item.get("value", "") for item in message.get("payload", {}).get("headers", [])
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
            {key: content[key] for key in ("draft_id", "recipients", "subject", "body", "thread_id")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return content


class GoogleActionUncertain(RuntimeError):
    """The request may have reached Google; it must not be blindly retried."""


async def send_draft(db: AsyncSession, user_id: str, connection_id: str, draft_id: str) -> dict:
    _, token = await _connection(db, user_id, "https://www.googleapis.com/auth/gmail.send", connection_id)
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


async def send_message(
    db: AsyncSession,
    user_id: str,
    to: list[str],
    subject: str,
    body: str,
    thread_id: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    connection_id: str | None = None,
) -> dict:
    if (
        not to
        or any("\n" in recipient or "\r" in recipient or "@" not in recipient for recipient in to)
        or "\n" in subject
        or "\r" in subject
        or len(subject) > 500
        or len(body) > 30000
    ):
        raise ValueError("Invalid recipients, subject, or email body")

    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject
    msg.set_content(body)

    raw_bytes = msg.as_bytes()
    raw_str = base64.urlsafe_b64encode(raw_bytes).decode().rstrip("=")
    req_body: dict[str, Any] = {"raw": raw_str}
    if thread_id:
        req_body["threadId"] = thread_id

    res = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/gmail.send",
        "POST",
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        connection_id=connection_id,
        json=req_body,
    )
    return {
        "status": "sent",
        "message_id": res.get("id"),
        "thread_id": res.get("threadId"),
        "to": to,
        "subject": subject,
    }


async def reply_to_thread(
    db: AsyncSession,
    user_id: str,
    thread_id: str,
    body: str,
    to: list[str] | None = None,
    subject: str | None = None,
    connection_id: str | None = None,
) -> dict:
    recipients = list(to or [])
    reply_subject = subject
    if not recipients or not reply_subject:
        thread_info = await get_thread(db, user_id, thread_id, limit=5)
        messages = thread_info.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if not recipients:
                sender = last_msg.get("from", "")
                if "<" in sender and ">" in sender:
                    sender = sender.split("<")[1].split(">")[0]
                recipients = [sender] if sender else []
            if not reply_subject:
                orig_subj = last_msg.get("subject", "")
                reply_subject = orig_subj if orig_subj.lower().startswith("re:") else f"Re: {orig_subj}"
    if not recipients:
        raise ValueError("Could not determine reply recipient. Please specify 'to' explicitly.")
    if not reply_subject:
        reply_subject = "Re: (no subject)"
    return await send_message(
        db,
        user_id,
        to=recipients,
        subject=reply_subject,
        body=body,
        thread_id=thread_id,
        connection_id=connection_id,
    )


async def trash_message(
    db: AsyncSession,
    user_id: str,
    message_id: str,
    connection_id: str | None = None,
) -> dict:
    if not message_id or len(message_id) > 200:
        raise ValueError("Invalid message ID")
    res = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/gmail.modify",
        "POST",
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/trash",
        connection_id=connection_id,
    )
    return {"status": "trashed", "message_id": res.get("id", message_id)}


async def modify_labels(
    db: AsyncSession,
    user_id: str,
    message_id: str,
    add_labels: list[str] | None = None,
    remove_labels: list[str] | None = None,
    connection_id: str | None = None,
) -> dict:
    if not message_id or len(message_id) > 200:
        raise ValueError("Invalid message ID")
    body_data = {
        "addLabelIds": add_labels or [],
        "removeLabelIds": remove_labels or [],
    }
    res = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/gmail.modify",
        "POST",
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify",
        connection_id=connection_id,
        json=body_data,
    )
    return {
        "status": "updated",
        "message_id": res.get("id", message_id),
        "labels": res.get("labelIds", []),
    }


async def search_drive_files(
    db: AsyncSession,
    user_id: str,
    query: str | None = None,
    mime_type: str | None = None,
    limit: int = 15,
    connection_id: str | None = None,
) -> dict:
    bounded_limit = min(max(int(limit), 1), 30)
    clauses = ["trashed = false"]
    if query and query.strip():
        sanitized = query.strip().replace("\\", "\\\\").replace("'", "\\'")
        clauses.append(f"(name contains '{sanitized}' or fullText contains '{sanitized}')")
    if mime_type and mime_type.strip():
        mt = mime_type.strip().lower()
        type_mapping = {
            "document": "application/vnd.google-apps.document",
            "doc": "application/vnd.google-apps.document",
            "spreadsheet": "application/vnd.google-apps.spreadsheet",
            "sheet": "application/vnd.google-apps.spreadsheet",
            "presentation": "application/vnd.google-apps.presentation",
            "slide": "application/vnd.google-apps.presentation",
            "pdf": "application/pdf",
            "folder": "application/vnd.google-apps.folder",
        }
        resolved = type_mapping.get(mt, mt)
        sanitized_mt = resolved.replace("\\", "\\\\").replace("'", "\\'")
        clauses.append(f"mimeType = '{sanitized_mt}'")

    params = {
        "q": " and ".join(clauses),
        "pageSize": bounded_limit,
        "fields": "files(id, name, mimeType, modifiedTime, size, webViewLink)",
        "orderBy": "modifiedTime desc",
    }
    payload = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/drive.readonly",
        "GET",
        "https://www.googleapis.com/drive/v3/files",
        connection_id=connection_id,
        params=params,
    )
    files = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "mime_type": item.get("mimeType"),
            "modified_time": item.get("modifiedTime"),
            "size_bytes": item.get("size"),
            "link": item.get("webViewLink"),
        }
        for item in payload.get("files", [])
    ]
    return {"query": query, "files": files, "count": len(files)}


async def get_drive_file_content(
    db: AsyncSession,
    user_id: str,
    file_id: str,
    connection_id: str | None = None,
) -> dict:
    if not file_id or not isinstance(file_id, str) or len(file_id) > 250 or "/" in file_id or "\\" in file_id:
        raise ValueError("Invalid Google Drive file ID")

    meta = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/drive.readonly",
        "GET",
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        connection_id=connection_id,
        params={"fields": "id, name, mimeType, size, webViewLink"},
    )
    name = meta.get("name", "untitled")
    mime_type = meta.get("mimeType", "")

    if mime_type == "application/vnd.google-apps.document":
        text_content = await _request(
            db,
            user_id,
            "https://www.googleapis.com/auth/drive.readonly",
            "GET",
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
            connection_id=connection_id,
            as_text=True,
            params={"mimeType": "text/plain"},
        )
    elif mime_type == "application/vnd.google-apps.spreadsheet":
        text_content = await _request(
            db,
            user_id,
            "https://www.googleapis.com/auth/drive.readonly",
            "GET",
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
            connection_id=connection_id,
            as_text=True,
            params={"mimeType": "text/csv"},
        )
    else:
        text_content = await _request(
            db,
            user_id,
            "https://www.googleapis.com/auth/drive.readonly",
            "GET",
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            connection_id=connection_id,
            as_text=True,
            params={"alt": "media"},
        )

    content = text_content[:25000] if isinstance(text_content, str) else str(text_content)[:25000]
    return {
        "file_id": file_id,
        "name": name,
        "mime_type": mime_type,
        "content": content,
        "truncated": len(text_content) > 25000,
        "link": meta.get("webViewLink"),
    }


async def create_drive_file(
    db: AsyncSession,
    user_id: str,
    name: str,
    content: str,
    mime_type: str = "text/plain",
    folder_id: str | None = None,
    connection_id: str | None = None,
) -> dict:
    if not name or len(name) > 250:
        raise ValueError("File name is required and must be under 250 characters")

    type_mapping = {
        "document": "application/vnd.google-apps.document",
        "doc": "application/vnd.google-apps.document",
        "spreadsheet": "application/vnd.google-apps.spreadsheet",
        "sheet": "application/vnd.google-apps.spreadsheet",
        "text": "text/plain",
        "markdown": "text/markdown",
        "md": "text/markdown",
    }
    target_mime = type_mapping.get(mime_type.strip().lower(), mime_type.strip())
    upload_mime = "text/csv" if "spreadsheet" in target_mime else "text/plain"

    metadata: dict[str, Any] = {"name": name, "mimeType": target_mime}
    if folder_id:
        metadata["parents"] = [folder_id]

    boundary = "===drive_multipart_boundary_life_sandbox==="
    multipart_body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {upload_mime}; charset=UTF-8\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--\r\n"
    )

    res = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/drive.file",
        "POST",
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,mimeType,webViewLink",
        connection_id=connection_id,
        content=multipart_body.encode("utf-8"),
        headers={"Content-Type": f"multipart/related; boundary={boundary}"},
    )
    return {
        "status": "created",
        "file_id": res.get("id"),
        "name": res.get("name", name),
        "mime_type": res.get("mimeType", target_mime),
        "link": res.get("webViewLink"),
    }


async def update_drive_file_content(
    db: AsyncSession,
    user_id: str,
    file_id: str,
    content: str,
    mime_type: str = "text/plain",
    connection_id: str | None = None,
) -> dict:
    if not file_id or len(file_id) > 250:
        raise ValueError("Invalid Google Drive file ID")
    res = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/drive.file",
        "PATCH",
        f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?"
        "uploadType=media&fields=id,name,mimeType,webViewLink",
        connection_id=connection_id,
        content=content.encode("utf-8"),
        headers={"Content-Type": f"{mime_type}; charset=UTF-8"},
    )
    return {
        "status": "updated",
        "file_id": res.get("id", file_id),
        "name": res.get("name"),
        "link": res.get("webViewLink"),
    }


async def delete_drive_file(
    db: AsyncSession,
    user_id: str,
    file_id: str,
    permanent: bool = False,
    connection_id: str | None = None,
) -> dict:
    if not file_id or len(file_id) > 250:
        raise ValueError("Invalid Google Drive file ID")
    if permanent:
        await _request(
            db,
            user_id,
            "https://www.googleapis.com/auth/drive.file",
            "DELETE",
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            connection_id=connection_id,
        )
        return {"status": "deleted", "file_id": file_id}
    else:
        res = await _request(
            db,
            user_id,
            "https://www.googleapis.com/auth/drive.file",
            "PATCH",
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            connection_id=connection_id,
            json={"trashed": True},
        )
        return {"status": "trashed", "file_id": res.get("id", file_id)}


async def create_drive_folder(
    db: AsyncSession,
    user_id: str,
    name: str,
    parent_folder_id: str | None = None,
    connection_id: str | None = None,
) -> dict:
    if not name or len(name) > 250:
        raise ValueError("Invalid folder name")
    payload: dict[str, Any] = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_folder_id:
        payload["parents"] = [parent_folder_id]
    res = await _request(
        db,
        user_id,
        "https://www.googleapis.com/auth/drive.file",
        "POST",
        "https://www.googleapis.com/drive/v3/files?fields=id,name,mimeType,webViewLink",
        connection_id=connection_id,
        json=payload,
    )
    return {
        "status": "created",
        "folder_id": res.get("id"),
        "name": res.get("name", name),
        "link": res.get("webViewLink"),
    }
