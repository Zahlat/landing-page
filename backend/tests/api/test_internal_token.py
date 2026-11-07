from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from app.api.deps import require_internal_token
from app.main import build_v1_router, create_app


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


def _depends_on(dependant: Dependant, target: object) -> bool:
    return any(d.call is target or _depends_on(d, target) for d in dependant.dependencies)


def test_every_v1_route_requires_internal_token() -> None:
    """Guard for later phases: no /v1 route may skip the internal-token check."""
    application = create_app()
    v1_routes = [
        r for r in application.routes if isinstance(r, APIRoute) and r.path.startswith("/v1")
    ]
    for route in v1_routes:
        assert _depends_on(route.dependant, require_internal_token), route.path


def test_v1_router_carries_dependency() -> None:
    router = build_v1_router()
    assert any(d.dependency is require_internal_token for d in router.dependencies)
