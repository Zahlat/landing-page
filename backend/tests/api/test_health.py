from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.db import get_db
from app.main import create_app


async def test_health_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_needs_no_internal_token(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Internal-Token": "wrong"})
    assert resp.status_code == 200


async def test_health_db_down_returns_503(app: FastAPI, client: AsyncClient) -> None:
    class BrokenSession:
        async def execute(self, *_: Any, **__: Any) -> None:
            raise OSError("connection refused")

    async def _broken_db() -> AsyncIterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_db] = _broken_db
    resp = await client.get("/health")
    assert resp.status_code == 503
    assert resp.json() == {"error": {"code": "db_unavailable", "message": "Database unavailable."}}
    assert "connection refused" not in resp.text


async def test_unknown_path_uses_error_shape(client: AsyncClient) -> None:
    resp = await client.get("/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_docs_enabled_outside_prod(client: AsyncClient) -> None:
    assert (await client.get("/openapi.json")).status_code == 200


async def test_docs_disabled_in_prod(test_settings: Settings) -> None:
    prod_app = create_app(test_settings.model_copy(update={"environment": "prod"}))
    async with AsyncClient(transport=ASGITransport(app=prod_app), base_url="http://t") as c:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await c.get(path)).status_code == 404, path
