"""Authentication dependency for Go-to-research internal HTTP calls."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from .config import Settings


def require_internal_service(
    authorization: str | None = Header(default=None),
    x_internal_service_token: str | None = Header(default=None),
) -> None:
    expected = Settings.from_env().internal_service_token
    supplied = x_internal_service_token
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "internal_auth_required", "message": "valid service token required"},
        )

