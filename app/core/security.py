from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
from fastapi import Cookie, Header, HTTPException

from app.core.config import get_settings


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None = None
    name: str | None = None


async def current_principal(
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias="life_sandbox_session"),
) -> Principal:
    settings = get_settings()
    token = (
        authorization[7:]
        if authorization and authorization.startswith("Bearer ")
        else session_cookie
    )
    if settings.auth_mode == "development" and settings.app_env == "development" and not token:
        return Principal(user_id="local-user")
    if not token:
        raise HTTPException(
            status_code=401, detail={"code": "unauthorized", "message": "Bearer token required"}
        )
    try:
        claims = jwt.decode(
            token,
            settings.auth_secret or "",
            algorithms=["HS256"],
            issuer=settings.auth_issuer or "life-sandbox",
            audience=settings.auth_audience or "life-sandbox-web",
            options={"require": ["exp", "sub"]},
        )
        if datetime.fromtimestamp(claims["exp"], UTC) <= datetime.now(UTC):
            raise ValueError("expired")
        return Principal(
            user_id=str(claims["sub"]),
            email=claims.get("email"),
            name=claims.get("name"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=401, detail={"code": "unauthorized", "message": "Invalid bearer token"}
        ) from exc
