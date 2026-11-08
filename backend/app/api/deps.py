"""Shared FastAPI dependencies."""

import hmac
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import normalize_ip
from app.services.auth_service import AdminContext, AuthService
from app.services.message_service import ClientInfo

__all__ = [
    "client_info",
    "current_admin",
    "get_db",
    "get_settings_dep",
    "require_internal_token",
]

# Real tokens are 43 chars; anything far longer is junk and not worth hashing.
_MAX_BEARER_LEN = 256


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def require_internal_token(
    request: Request,
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    """Reject any request that does not carry the shared Next.js -> FastAPI secret."""
    expected = get_settings_dep(request).internal_token.get_secret_value().encode()
    supplied = (x_internal_token or "").encode()
    # compare_digest is constant-time for equal-length inputs; a length mismatch
    # simply returns False.
    if not hmac.compare_digest(supplied, expected):
        raise AppError(401, "unauthorized", "Unauthorized.")


def client_info(
    x_client_ip: Annotated[str | None, Header()] = None,
    x_client_ua: Annotated[str | None, Header()] = None,
) -> ClientInfo:
    """Visitor IP/UA as forwarded by Next.js.

    Trusted only because require_internal_token already proved the caller is Next.js.
    The socket peer (request.client) is Next.js itself, so it is deliberately ignored.
    """
    ua = x_client_ua.strip() if x_client_ua else None
    return ClientInfo(ip=normalize_ip(x_client_ip), user_agent=ua or None)


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or len(token) > _MAX_BEARER_LEN:
        return None
    return token


async def current_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    authorization: Annotated[str | None, Header()] = None,
) -> AdminContext:
    """Admin from `Authorization: Bearer <session token>`; 401 for anything else.
    Runs after require_internal_token (router-level dependencies run first)."""
    token = _bearer_token(authorization)
    if token is None:
        raise AppError(401, "unauthorized", "Unauthorized.")
    return await AuthService(db, settings).authenticate(token)
