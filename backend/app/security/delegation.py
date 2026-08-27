"""Verification for short-lived delegation tokens issued by NexDokandar."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import InvalidTokenError

from app.core.config import Settings, get_settings
from app.models.request_context import SaaSRequestContext


def _unauthorized(detail: str = "Invalid service authentication") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _normalize_public_key(public_key: str) -> str:
    """Allow PEM keys to be stored with escaped newlines in environment values."""
    return public_key.strip().replace("\\n", "\n")


def verify_internal_service_key(provided_key: str | None, settings: Settings) -> None:
    expected_key = settings.saas_internal_service_key
    if not provided_key or not expected_key:
        raise _unauthorized()
    if not secrets.compare_digest(provided_key, expected_key):
        raise _unauthorized()


def verify_delegation_token(token: str, settings: Settings) -> SaaSRequestContext:
    """Verify a SaaS-issued RS256 token and build immutable trusted context."""
    public_key = _normalize_public_key(settings.saas_delegation_public_key)
    if not public_key:
        raise _unauthorized("Delegation verification is not configured")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.saas_delegation_audience,
            issuer=settings.saas_delegation_issuer,
            leeway=settings.saas_delegation_clock_skew_seconds,
            options={
                "require": [
                    "exp", "iat", "iss", "aud", "sub", "jti", "org_id", "role"
                ]
            },
        )
    except InvalidTokenError as exc:
        raise _unauthorized("Invalid or expired delegation token") from exc

    now = datetime.now(timezone.utc)
    issued_at = datetime.fromtimestamp(float(claims["iat"]), tz=timezone.utc)
    expires_at = datetime.fromtimestamp(float(claims["exp"]), tz=timezone.utc)
    token_age = (now - issued_at).total_seconds()

    if token_age < -settings.saas_delegation_clock_skew_seconds:
        raise _unauthorized("Delegation token was issued in the future")
    if token_age > settings.saas_delegation_max_age_seconds:
        raise _unauthorized("Delegation token is too old")

    try:
        return SaaSRequestContext(
            user_id=claims["sub"],
            org_id=claims["org_id"],
            role=claims["role"],
            allowed_location_ids=tuple(claims.get("allowed_location_ids") or ()),
            selected_location_id=claims.get("selected_location_id"),
            permissions=frozenset(claims.get("permissions") or ()),
            features=frozenset(claims.get("features") or ()),
            locale=claims.get("locale") or "en-BD",
            timezone=claims.get("timezone") or "Asia/Dhaka",
            request_id=claims.get("request_id") or claims["jti"],
            token_id=claims["jti"],
            issued_at=issued_at,
            expires_at=expires_at,
        )
    except (TypeError, ValueError) as exc:
        raise _unauthorized("Delegation token contains invalid scope claims") from exc


async def get_saas_request_context(
    authorization: Annotated[str | None, Header()] = None,
    x_zenai_service_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> SaaSRequestContext:
    verify_internal_service_key(x_zenai_service_key, settings)
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized("Missing delegation token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise _unauthorized("Missing delegation token")
    return verify_delegation_token(token, settings)


async def require_internal_service(
    x_zenai_service_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """Authenticate infrastructure endpoints that do not need user delegation."""
    verify_internal_service_key(x_zenai_service_key, settings)

