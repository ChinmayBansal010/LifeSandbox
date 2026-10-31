import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import Principal, current_principal
from app.persistence.models import IntegrationConnectionRow, OAuthStateRow
from app.persistence.session import get_session

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
GOOGLE_SCOPE = {
    "calendar.read": "https://www.googleapis.com/auth/calendar.readonly",
    "calendar.events": "https://www.googleapis.com/auth/calendar.events",
    "calendar.write": "https://www.googleapis.com/auth/calendar",
    "gmail.read": "https://www.googleapis.com/auth/gmail.readonly",
    "gmail.draft": "https://www.googleapis.com/auth/gmail.compose",
    "gmail.send": "https://www.googleapis.com/auth/gmail.send",
    "gmail.modify": "https://www.googleapis.com/auth/gmail.modify",
    "drive.read": "https://www.googleapis.com/auth/drive.readonly",
    "drive.file": "https://www.googleapis.com/auth/drive.file",
    "drive.write": "https://www.googleapis.com/auth/drive",
}


def credential_cipher() -> Fernet:
    key = get_settings().google_token_encryption_key
    if not key:
        raise HTTPException(
            503,
            detail={
                "code": "token_encryption_unconfigured",
                "message": "Google connections are unavailable until encryption is configured.",
            },
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(
            503,
            detail={
                "code": "token_encryption_invalid",
                "message": "Google token encryption configuration is invalid.",
            },
        ) from exc


def encrypt_credentials(value: dict) -> str:
    return credential_cipher().encrypt(json.dumps(value).encode()).decode()


def decrypt_credentials(value: str) -> dict:
    try:
        return json.loads(credential_cipher().decrypt(value.encode()))
    except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            503,
            detail={
                "code": "connection_credentials_invalid",
                "message": "Reconnect the Google account to continue.",
            },
        ) from exc


class ConnectRequest(BaseModel):
    capabilities: list[str] = Field(min_length=1, max_length=20)


def public_connection(row: IntegrationConnectionRow):
    scopes = json.loads(row.scopes)
    return {
        "id": row.id,
        "provider": row.provider,
        "account_email": row.account_email,
        "capabilities": [name for name, scope in GOOGLE_SCOPE.items() if scope in scopes],
        "status": row.status,
    }


def _settings():
    config = get_settings()
    if not all(
        (
            config.google_oauth_client_id,
            config.google_oauth_client_secret,
            config.google_oauth_callback_url,
        )
    ):
        raise HTTPException(
            503,
            detail={
                "code": "google_oauth_unconfigured",
                "message": "Google OAuth client ID, secret, and callback URL must be configured.",
            },
        )
    credential_cipher()
    return config


@router.get("")
async def connections(
    principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_session)
):
    rows = (
        await db.scalars(
            select(IntegrationConnectionRow).where(
                IntegrationConnectionRow.user_id == principal.user_id
            )
        )
    ).all()
    config = get_settings()
    configured = all(
        (
            config.google_oauth_client_id,
            config.google_oauth_client_secret,
            config.google_oauth_callback_url,
            config.google_token_encryption_key,
        )
    )
    return {
        "connections": [public_connection(row) for row in rows],
        "configured": configured,
    }


async def create_google_authorization_url(
    user_id: str,
    db: AsyncSession,
    capabilities: list[str] | None = None,
) -> str:
    config = _settings()
    caps = capabilities if capabilities is not None else list(GOOGLE_SCOPE.keys())
    if any(cap not in GOOGLE_SCOPE for cap in caps):
        raise HTTPException(
            422,
            detail={
                "code": "invalid_capability",
                "message": "One or more Google capabilities are unsupported.",
            },
        )
    scopes = sorted({GOOGLE_SCOPE[cap] for cap in caps})
    raw_state = secrets.token_urlsafe(40)
    db.add(
        OAuthStateRow(
            state_hash=hashlib.sha256(raw_state.encode()).hexdigest(),
            user_id=user_id,
            scopes=json.dumps(scopes),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    await db.commit()
    params = {
        "client_id": config.google_oauth_client_id,
        "redirect_uri": config.google_oauth_callback_url,
        "response_type": "code",
        "scope": " ".join(scopes + ["openid", "email"]),
        "state": raw_state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


@router.post("/google/authorize")
async def authorize_google(
    payload: ConnectRequest,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    url = await create_google_authorization_url(
        user_id=principal.user_id, db=db, capabilities=payload.capabilities
    )
    return {"authorization_url": url}


async def complete_google_callback(
    code: str,
    state: str,
    db: AsyncSession,
) -> dict[str, Any]:
    config = _settings()
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    now = datetime.now(UTC)
    consumed = await db.execute(
        update(OAuthStateRow)
        .where(
            OAuthStateRow.state_hash == state_hash,
            OAuthStateRow.consumed_at.is_(None),
            OAuthStateRow.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(OAuthStateRow.user_id, OAuthStateRow.scopes)
    )
    owner_scopes = consumed.one_or_none()
    if owner_scopes is None:
        raise HTTPException(
            400,
            detail={
                "code": "oauth_state_invalid",
                "message": "Authorization state expired or used. Start a new connection with /connect_google.",
            },
        )
    owner, scopes = owner_scopes.user_id, owner_scopes.scopes
    await db.commit()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": config.google_oauth_client_id,
                    "client_secret": config.google_oauth_client_secret,
                    "redirect_uri": config.google_oauth_callback_url,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            tokens = response.json()
            info_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            info_response.raise_for_status()
            info = info_response.json()
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(
            502,
            detail={
                "code": "google_oauth_exchange_failed",
                "message": "Google authorization could not be completed. Start a new connection.",
            },
        ) from exc
    token_scopes = sorted(set(tokens.get("scope", "").split()) & set(json.loads(scopes)))
    row = await db.scalar(
        select(IntegrationConnectionRow).where(
            IntegrationConnectionRow.user_id == owner,
            IntegrationConnectionRow.provider == "google",
            IntegrationConnectionRow.account_email == info.get("email"),
            IntegrationConnectionRow.status == "connected",
        )
    )
    credential_payload = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "token_type": tokens.get("token_type", "Bearer"),
    }
    expires_in = int(tokens.get("expires_in", 3600))
    if row:
        previous = decrypt_credentials(row.encrypted_credentials)
        if not credential_payload["refresh_token"]:
            credential_payload["refresh_token"] = previous.get("refresh_token")
        row.encrypted_credentials = encrypt_credentials(credential_payload)
        row.scopes = json.dumps(token_scopes)
        row.expires_at = now + timedelta(seconds=expires_in)
    else:
        row = IntegrationConnectionRow(
            user_id=owner,
            provider="google",
            account_email=info.get("email"),
            scopes=json.dumps(token_scopes),
            encrypted_credentials=encrypt_credentials(credential_payload),
            expires_at=now + timedelta(seconds=expires_in),
            status="connected",
        )
        db.add(row)
    await db.commit()
    return {
        "connected": True,
        "connection": public_connection(row),
        "account_email": row.account_email,
        "token_scopes": token_scopes,
        "message": "Google account connected. You can close this page.",
    }


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(min_length=1),
    state: str = Query(min_length=20),
    db: AsyncSession = Depends(get_session),
):
    result = await complete_google_callback(code=code, state=state, db=db)
    config = _settings()
    if "text/html" in request.headers.get("accept", ""):
        frontend_url = config.google_auth_frontend_url.rstrip("/")
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Google Account Connected</title>
    <style>
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            background: #09090b;
            color: #fafafa;
        }}
        .card {{
            text-align: center;
            padding: 2rem;
            border-radius: 1rem;
            border: 1px solid #27272a;
            background: #18181b;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            max-width: 400px;
        }}
        h1 {{ font-size: 1.25rem; margin-bottom: 0.5rem; color: #10b981; }}
        p {{ font-size: 0.875rem; color: #a1a1aa; line-height: 1.5; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>✓ Google Account Connected</h1>
        <p>Your Google integration is active. This window will close automatically.</p>
    </div>
    <script>
        if (window.opener) {{
            window.opener.postMessage({{ type: 'GOOGLE_CONNECTED' }}, '*');
            setTimeout(() => window.close(), 500);
        }} else {{
            window.location.href = "{frontend_url}/?integration=google_connected";
        }}
    </script>
</body>
</html>"""
        return HTMLResponse(content=html)

    return result


@router.delete("/{connection_id}")
async def disconnect(
    connection_id: str,
    principal: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(IntegrationConnectionRow).where(
            IntegrationConnectionRow.id == connection_id,
            IntegrationConnectionRow.user_id == principal.user_id,
            IntegrationConnectionRow.status == "connected",
        )
    )
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Connection not found."})
    creds = decrypt_credentials(row.encrypted_credentials)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": creds.get("refresh_token") or creds["access_token"]},
            )
    except httpx.HTTPError:
        pass
    row.status = "disconnected"
    row.encrypted_credentials = encrypt_credentials({})
    await db.commit()
    return {"disconnected": True}
