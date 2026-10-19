"""Google OpenID Connect sign-in and signed app-session endpoints."""

import asyncio
import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from jwt import InvalidTokenError, PyJWKClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import Principal, current_principal
from app.persistence.models import GoogleLoginStateRow
from app.persistence.session import get_session

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
SESSION_COOKIE = "life_sandbox_session"
STATE_COOKIE = "life_sandbox_oauth_state"
SESSION_MAX_AGE = 60 * 60 * 8


def _configuration():
    settings = get_settings()
    if not all(
        (
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
            settings.google_auth_callback_url,
            settings.google_auth_frontend_url,
            settings.auth_secret,
        )
    ):
        raise HTTPException(
            503,
            detail={
                "code": "google_signin_unconfigured",
                "message": (
                    "Google sign-in needs OAuth client credentials, a sign-in callback URL, "
                    "and AUTH_SECRET."
                ),
            },
        )
    return settings


def _verify_google_id_token(token: str, client_id: str, expected_nonce: str) -> dict:
    key_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, timeout=5)
    signing_key = key_client.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=GOOGLE_ISSUERS,
        options={"require": ["exp", "iat", "sub", "aud", "nonce"]},
    )
    if claims.get("nonce") != expected_nonce:
        raise InvalidTokenError("Google ID token nonce did not match")
    if claims.get("email_verified") is not True:
        raise InvalidTokenError("Google account email is not verified")
    return claims


async def _exchange_google_code(code: str, verifier: str, settings) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_auth_callback_url,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
        token_response.raise_for_status()
        return token_response.json()["id_token"]


@router.get("/google/start")
async def google_signin_start(db: AsyncSession = Depends(get_session)):
    settings = _configuration()
    state = secrets.token_urlsafe(40)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    challenge = challenge.rstrip(b"=").decode("ascii")
    db.add(
        GoogleLoginStateRow(
            state_hash=hashlib.sha256(state.encode()).hexdigest(),
            nonce=nonce,
            code_verifier=verifier,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    await db.commit()
    query = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_auth_callback_url,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    redirect = RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=302
    )
    redirect.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/api/v1/auth/google/callback",
    )
    return redirect


@router.get("/google/status")
async def google_signin_status():
    settings = get_settings()
    configured = bool(
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.google_auth_callback_url
        and settings.auth_secret
    )
    return {
        "configured": configured,
        "message": (
            "Google sign-in is ready."
            if configured
            else "Configure Google OAuth credentials, GOOGLE_AUTH_CALLBACK_URL, and AUTH_SECRET."
        ),
    }


@router.get("/google/callback")
async def google_signin_callback(
    state: str = Query(min_length=20),
    state_cookie: str | None = Cookie(default=None, alias=STATE_COOKIE),
    code: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    settings = _configuration()
    frontend_url = settings.google_auth_frontend_url.rstrip("/")
    if not state_cookie or not secrets.compare_digest(state, state_cookie):
        raise HTTPException(
            400,
            detail={
                "code": "oauth_state_invalid",
                "message": "Sign-in state is invalid. Start again.",
            },
        )
    if error:
        redirect = RedirectResponse(f"{frontend_url}/?auth=denied", status_code=303)
        redirect.delete_cookie(STATE_COOKIE, path="/api/v1/auth/google/callback")
        return redirect
    if not code:
        raise HTTPException(
            400,
            detail={
                "code": "oauth_code_missing",
                "message": "Google did not return an authorization code.",
            },
        )

    client_id = settings.google_oauth_client_id
    session_secret = settings.auth_secret
    assert client_id is not None and session_secret is not None
    now = datetime.now(UTC)
    consumed = await db.execute(
        update(GoogleLoginStateRow)
        .where(
            GoogleLoginStateRow.state_hash == hashlib.sha256(state.encode()).hexdigest(),
            GoogleLoginStateRow.consumed_at.is_(None),
            GoogleLoginStateRow.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(GoogleLoginStateRow.nonce, GoogleLoginStateRow.code_verifier)
    )
    login_state = consumed.one_or_none()
    if login_state is None:
        raise HTTPException(
            400,
            detail={
                "code": "oauth_state_invalid",
                "message": "Sign-in expired or was already used. Start again.",
            },
        )
    await db.commit()

    try:
        id_token = await _exchange_google_code(code, login_state.code_verifier, settings)
        claims = await asyncio.wait_for(
            asyncio.to_thread(
                _verify_google_id_token,
                id_token,
                client_id,
                login_state.nonce,
            ),
            timeout=8,
        )
    except (httpx.HTTPError, KeyError, ValueError, InvalidTokenError, TimeoutError) as exc:
        raise HTTPException(
            502,
            detail={
                "code": "google_signin_failed",
                "message": "Google sign-in could not be verified. Start again and retry.",
            },
        ) from exc

    issuer = settings.auth_issuer or "life-sandbox"
    audience = settings.auth_audience or "life-sandbox-web"
    session_token = jwt.encode(
        {
            "sub": f"google:{claims['sub']}",
            "email": claims.get("email"),
            "name": claims.get("name"),
            "iss": issuer,
            "aud": audience,
            "iat": now,
            "exp": now + timedelta(seconds=SESSION_MAX_AGE),
        },
        session_secret,
        algorithm="HS256",
    )
    redirect = RedirectResponse(f"{frontend_url}/?auth=success", status_code=303)
    redirect.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )
    redirect.delete_cookie(STATE_COOKIE, path="/api/v1/auth/google/callback")
    return redirect


@router.get("/me")
async def current_user(principal: Principal = Depends(current_principal)):
    return {
        "user_id": principal.user_id,
        "email": principal.email,
        "name": principal.name,
        "authenticated": principal.email is not None,
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=get_settings().app_env == "production",
        samesite="lax",
        path="/",
    )
    return {"logged_out": True}
