"""Shared FastAPI dependencies."""

import hmac
from typing import Annotated

from fastapi import Header, Request

from app.core.config import Settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import normalize_ip
from app.services.message_service import ClientInfo

__all__ = ["client_info", "get_db", "get_settings_dep", "require_internal_token"]


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
