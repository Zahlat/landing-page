from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import require_internal_token
from app.main import build_v1_router
from tests.route_guards import documented_routes, routes_not_rejected


@pytest.fixture
async def probe_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """App with throwaway /v1 routes mounted through the real v1 router factory."""
    router = build_v1_router()

    @router.get("/_probe")
    async def probe() -> dict[str, str]:
        return {"ok": "yes"}

    @router.get("/_boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    @router.get("/_typed")
    async def typed(n: int) -> dict[str, int]:
        return {"n": n}

    app.include_router(router)
    # raise_app_exceptions=False lets us see the 500 response instead of the re-raise.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_missing_token_401(probe_client: AsyncClient) -> None:
    resp = await probe_client.get("/v1/_probe")
    assert resp.status_code == 401
    assert resp.json() == {"error": {"code": "unauthorized", "message": "Unauthorized."}}


@pytest.mark.parametrize("token", ["", "wrong", "x" * 200])
async def test_wrong_token_401(probe_client: AsyncClient, token: str) -> None:
    resp = await probe_client.get("/v1/_probe", headers={"X-Internal-Token": token})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_correct_token_200(
    probe_client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    resp = await probe_client.get("/v1/_probe", headers=internal_headers)
    assert resp.status_code == 200
    assert resp.json() == {"ok": "yes"}


async def test_token_checked_before_validation(probe_client: AsyncClient) -> None:
    # No token + invalid query: auth must win, so callers learn nothing about the route.
    resp = await probe_client.get("/v1/_typed", params={"n": "abc"})
    assert resp.status_code == 401


async def test_validation_error_shape(
    probe_client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    resp = await probe_client.get("/v1/_typed", params={"n": "abc"}, headers=internal_headers)
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    assert err["fields"][0]["loc"] == ["query", "n"]
    assert "abc" not in resp.text  # submitted values are never echoed back


async def test_unhandled_error_hides_details(
    probe_client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    resp = await probe_client.get("/v1/_boom", headers=internal_headers)
    assert resp.status_code == 500
    assert resp.json() == {"error": {"code": "internal_error", "message": "Internal server error."}}
    assert "secret internal detail" not in resp.text
    assert "Traceback" not in resp.text


async def test_every_v1_route_requires_internal_token(app: FastAPI, client: AsyncClient) -> None:
    """Guard for later phases: no /v1 route may skip the internal-token check."""
    routes = documented_routes(app, "/v1")
    # Non-vacuous: if route discovery ever breaks, this fails instead of checking nothing.
    assert {("POST", "/v1/messages"), ("POST", "/v1/admin/auth/login")} <= set(routes)
    assert await routes_not_rejected(client, routes) == []


async def test_route_guard_detects_an_unprotected_route(app: FastAPI, client: AsyncClient) -> None:
    """Proves the guard above can fail: a router without the dependency gets caught."""
    unprotected = APIRouter(prefix="/v1")

    @unprotected.get("/leak")
    async def leak() -> dict[str, str]:
        return {"secret": "data"}

    app.include_router(unprotected)
    routes = documented_routes(app, "/v1")
    assert await routes_not_rejected(client, routes) == [("GET", "/v1/leak")]


def test_v1_router_carries_dependency() -> None:
    router = build_v1_router()
    assert any(d.dependency is require_internal_token for d in router.dependencies)
