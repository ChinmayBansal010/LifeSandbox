from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
from fastapi import Header, HTTPException

from app.core.config import get_settings


@dataclass(frozen=True)
class Principal:
    user_id: str


async def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    settings = get_settings()
    if settings.auth_mode == "development" and settings.app_env == "development":
        return Principal(user_id="local-user")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail={"code": "unauthorized", "message": "Bearer token required"}
        )
    try:
        claims = jwt.decode(
            authorization[7:],
            settings.auth_secret or "",
            algorithms=["HS256"],
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
            options={"require": ["exp", "sub"]},
        )
        if datetime.fromtimestamp(claims["exp"], UTC) <= datetime.now(UTC):
            raise ValueError("expired")
        return Principal(user_id=str(claims["sub"]))
    except Exception as exc:
        raise HTTPException(
            status_code=401, detail={"code": "unauthorized", "message": "Invalid bearer token"}
        ) from exc
