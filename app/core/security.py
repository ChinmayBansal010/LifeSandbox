from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
from fastapi import Cookie, Depends, Header, HTTPException

from app.core.config import get_settings


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None


async def current_principal(
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias="life_sandbox_session"),
) -> Principal:
    settings = get_settings()
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else session_cookie
    if settings.auth_mode == "development" and settings.app_env == "development" and not token:
        return Principal(user_id="local-user")
    if not token:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Bearer token required"})

    # Check local HS256 session token first
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
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("subject must be a non-empty string")
        return Principal(
            user_id=subject.strip(),
            email=claims.get("email"),
            name=claims.get("name"),
            picture=claims.get("picture"),
        )
    except Exception as local_err:
        # shortcut: Neon Auth JWKS verification supports standard Neon Auth RS256/ES256 JWTs, upgrade to database session polling if stateful revocations are required.
        if settings.neon_auth_url:
            try:
                neon_jwks_url = f"{settings.neon_auth_url.rstrip('/')}/.well-known/jwks.json"
                key_client = jwt.PyJWKClient(neon_jwks_url, cache_keys=True, timeout=5)
                signing_key = key_client.get_signing_key_from_jwt(token)
                neon_claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256", "EdDSA"],
                    options={"verify_aud": False},
                )
                sub = neon_claims.get("sub") or neon_claims.get("id")
                if sub and isinstance(sub, str):
                    return Principal(
                        user_id=f"neon:{sub.strip()}",
                        email=neon_claims.get("email"),
                        name=neon_claims.get("name"),
                        picture=neon_claims.get("image") or neon_claims.get("picture"),
                    )
            except Exception:
                pass
        raise HTTPException(
            status_code=401, detail={"code": "unauthorized", "message": "Invalid bearer token"}
        ) from local_err


async def require_admin(principal: Principal = Depends(current_principal)) -> Principal:
    """Require a principal explicitly allowlisted by the deployment operator."""
    if principal.user_id not in get_settings().admin_user_ids:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Administrator access required"},
        )
    return principal
