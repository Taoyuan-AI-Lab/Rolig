import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import InvalidTokenError, PyJWK, PyJWKClient
from jwt.exceptions import PyJWKClientError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import Settings, get_settings

JWKS_CACHE_SECONDS = 600
JWKS_FETCH_TIMEOUT_SECONDS = 5
EXPECTED_AUDIENCE = "authenticated"


class JWTClaims(BaseModel):
    model_config = ConfigDict(extra="allow")

    sub: UUID
    exp: int
    iss: str
    aud: str | list[str]
    role: str | None = None
    app_metadata: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: UUID
    is_admin: bool


class SigningKeyProvider(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> PyJWK: ...


@lru_cache(maxsize=8)
def get_jwks_client(jwks_url: str) -> PyJWKClient:
    # Supabase publishes only public verification keys here. PyJWKClient caches
    # the set while still refreshing it when a previously unseen `kid` appears
    # during a safe signing-key rotation.
    return PyJWKClient(
        jwks_url,
        cache_jwk_set=True,
        lifespan=JWKS_CACHE_SECONDS,
        timeout=JWKS_FETCH_TIMEOUT_SECONDS,
    )


def verify_session_token(
    token: str,
    *,
    jwks_client: SigningKeyProvider,
    issuer: str,
) -> AuthenticatedUser:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=["ES256"],
            audience=EXPECTED_AUDIENCE,
            issuer=issuer,
            options={
                "require": ["aud", "exp", "iss", "role", "sub"],
                "verify_signature": True,
            },
        )
        claims = JWTClaims.model_validate(payload)
    except (InvalidTokenError, PyJWKClientError, TypeError, ValueError, ValidationError) as exc:
        raise ValueError("invalid session token") from exc

    if claims.role not in {"authenticated", "admin"}:
        raise ValueError("invalid session token")
    metadata_role = claims.app_metadata.get("role")
    is_admin = claims.role == "admin" or metadata_role == "admin"
    return AuthenticatedUser(id=claims.sub, is_admin=is_admin)


async def get_authenticated_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    authorization = request.headers.get("authorization", "")
    token: str | None = None
    if authorization:
        scheme, separator, credentials = authorization.partition(" ")
        if separator and scheme.lower() == "bearer":
            token = credentials.strip()
    if token is None:
        token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    if len(token) > 4096:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
        )
    issuer = f"{str(settings.supabase_url).rstrip('/')}/auth/v1"
    jwks_url = f"{issuer}/.well-known/jwks.json"
    try:
        return await asyncio.to_thread(
            verify_session_token,
            token,
            jwks_client=get_jwks_client(jwks_url),
            issuer=issuer,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
        ) from exc


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
