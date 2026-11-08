"""Black-box route guards: list every documented route, then really call it.

Deliberately doesn't inspect app.routes or dependency trees. FastAPI's internal route
storage changes between versions (included routers are nested, not flattened), and a
scan of it can silently match nothing.
"""

import re

from fastapi import FastAPI
from httpx import AsyncClient

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
UNAUTHORIZED = {"error": {"code": "unauthorized", "message": "Unauthorized."}}


def documented_routes(app: FastAPI, prefix: str) -> list[tuple[str, str]]:
    """(METHOD, path template) for every route in the OpenAPI schema under prefix."""
    return [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(prefix)
        for method in operations
        if method in _HTTP_METHODS
    ]


async def routes_not_rejected(
    client: AsyncClient,
    routes: list[tuple[str, str]],
    headers: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Routes that did NOT answer 401 unauthorized when called with these headers."""
    failures: list[tuple[str, str]] = []
    for method, path in routes:
        url = re.sub(r"\{[^}]+\}", "1", path)
        resp = await client.request(method, url, headers=headers or {})
        if resp.status_code != 401 or resp.json() != UNAUTHORIZED:
            failures.append((method, path))
    return failures
