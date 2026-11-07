"""Shared FastAPI dependencies."""

import hmac
from typing import Annotated

from fastapi import Header, Request

from app.core.config import Settings
from app.core.db import get_db
from app.core.errors import AppError

__all__ = ["get_db", "get_settings_dep", "require_internal_token"]


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
