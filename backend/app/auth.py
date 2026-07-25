import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import Settings, get_settings


class JWTClaims(BaseModel):
    model_config = ConfigDict(extra="allow")

    sub: UUID
    exp: int
    role: str | None = None
    app_metadata: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: UUID
    is_admin: bool


def _decode_segment(segment: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid session token") from exc


def verify_session_token(token: str, secret: str) -> AuthenticatedUser:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_decode_segment(encoded_header))
        if header.get("alg") != "HS256":
            raise ValueError("invalid session token")
        signing_input = f"{encoded_header}.{encoded_payload}".encode()
        expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        signature = _decode_segment(encoded_signature)
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid session token")
        claims = JWTClaims.model_validate_json(_decode_segment(encoded_payload))
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("invalid session token") from exc

    if claims.exp <= int(time.time()):
        raise ValueError("session token has expired")
    if claims.role not in {"authenticated", "admin", "service_role"}:
        raise ValueError("invalid session token")
    metadata_role = claims.app_metadata.get("role")
    is_admin = claims.role in {"admin", "service_role"} or metadata_role == "admin"
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
    try:
        return verify_session_token(token, settings.supabase_jwt_secret.get_secret_value())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
        ) from exc


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
