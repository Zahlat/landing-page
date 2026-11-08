from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_session import AdminSession
from app.models.contact_message import ContactMessage
from app.models.enums import Locale, MessageStatus, MessageType
from tests.factories import create_admin_session, insert_message
from tests.route_guards import UNAUTHORIZED, documented_routes, routes_not_rejected

URL = "/v1/admin/messages"
STATS = f"{URL}/stats"
NOT_FOUND = {"error": {"code": "not_found", "message": "Message not found."}}
OLD_READ_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def admin_headers(
    db_session: AsyncSession, internal_headers: dict[str, str]
) -> dict[str, str]:
    token = await create_admin_session(db_session)
    return {**internal_headers, "Authorization": f"Bearer {token}"}


async def list_page(client: AsyncClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    resp = await client.get(URL, params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()
    return data


async def walk(client: AsyncClient, headers: dict[str, str], **params: Any) -> list[int]:
    """Follow next_cursor to the end; returns every id in order."""
    ids: list[int] = []
    cursor: str | None = None
    for _ in range(200):
        query = {**params, **({"cursor": cursor} if cursor else {})}
        page = await list_page(client, headers, **query)
        ids += [item["id"] for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            return ids
    raise AssertionError("pagination did not terminate")


async def db_row(db: AsyncSession, message_id: int) -> Any:
    stmt = sa.select(ContactMessage.status, ContactMessage.read_at).where(
        ContactMessage.id == message_id
    )
    return (await db.execute(stmt)).one_or_none()


# --- auth ---------------------------------------------------------------------------


EXPECTED_ROUTES = {
    ("GET", URL),
    ("GET", STATS),
    ("GET", f"{URL}/{{message_id}}"),
    ("PATCH", f"{URL}/{{message_id}}"),
    ("DELETE", f"{URL}/{{message_id}}"),
}


async def test_every_route_rejects_missing_internal_token(
    app: FastAPI, client: AsyncClient
) -> None:
    routes = documented_routes(app, URL)
    assert set(routes) == EXPECTED_ROUTES
    assert await routes_not_rejected(client, routes) == []


async def test_every_route_rejects_missing_session(
    app: FastAPI, client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    routes = documented_routes(app, URL)
    assert set(routes) == EXPECTED_ROUTES
    assert await routes_not_rejected(client, routes, internal_headers) == []


async def test_every_route_rejects_session_without_internal_token(
    app: FastAPI, client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    only_bearer = {"Authorization": admin_headers["Authorization"]}
    assert await routes_not_rejected(client, documented_routes(app, URL), only_bearer) == []


async def test_every_route_rejects_expired_session(
    app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await db_session.execute(
        sa.update(AdminSession).values(
            created_at=sa.func.now() - sa.text("interval '9 hours'"),
            expires_at=sa.func.now() - sa.text("interval '1 hour'"),
        )
    )
    assert await routes_not_rejected(client, documented_routes(app, URL), admin_headers) == []


async def test_unauthenticated_delete_changes_nothing(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    msg = await insert_message(db_session)
    resp = await client.delete(f"{URL}/{msg.id}", headers=internal_headers)
    assert resp.status_code == 401
    assert resp.json() == UNAUTHORIZED
    assert await db_row(db_session, msg.id) is not None


# --- list: shape and preview --------------------------------------------------------


async def test_list_item_fields(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    msg = await insert_message(
        db_session,
        name="Sara",
        email="sara@example.com",
        type=MessageType.REQUEST,
        content="A short message body",
    )
    page = await list_page(client, admin_headers)
    assert page["next_cursor"] is None
    assert len(page["items"]) == 1
    item = page["items"][0]
    assert set(item) == {"id", "created_at", "name", "email", "type", "status", "preview"}
    assert item["id"] == msg.id
    assert item["name"] == "Sara"
    assert item["email"] == "sara@example.com"
    assert item["type"] == "request"
    assert item["status"] == "new"
    assert item["preview"] == "A short message body"


@pytest.mark.parametrize(
    ("length", "char"), [(160, "c"), (161, "c"), (5000, "c"), (161, "ع")], ids=str
)
async def test_preview_is_first_160_chars(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
    length: int,
    char: str,
) -> None:
    await insert_message(db_session, content=char * length)
    item = (await list_page(client, admin_headers))["items"][0]
    assert item["preview"] == char * 160


async def test_empty_list(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    assert await list_page(client, admin_headers) == {"items": [], "next_cursor": None}


# --- list: pagination ---------------------------------------------------------------


@pytest.mark.parametrize("limit", [1, 2, 3, 7, 15, 50])
async def test_pagination_no_gaps_or_duplicates_with_equal_created_at(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
    limit: int,
) -> None:
    # Three groups of rows; every row in a group has exactly the same created_at.
    expected: list[int] = []
    for minutes in (0, 1, 2):
        now = (await db_session.execute(sa.select(sa.func.now()))).scalar_one()
        moment = now - timedelta(minutes=minutes)
        group = [(await insert_message(db_session, created_at=moment)).id for _ in range(5)]
        expected += sorted(group, reverse=True)

    assert await walk(client, admin_headers, limit=limit) == expected


async def test_default_limit_is_20(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    for _ in range(21):
        await insert_message(db_session)
    page = await list_page(client, admin_headers)
    assert len(page["items"]) == 20
    assert page["next_cursor"] is not None


async def test_exactly_full_last_page_has_no_cursor(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    for _ in range(2):
        await insert_message(db_session)
    page = await list_page(client, admin_headers, limit=2)
    assert len(page["items"]) == 2
    assert page["next_cursor"] is None


async def test_new_message_between_pages_causes_no_duplicate(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    ids = [(await insert_message(db_session)).id for _ in range(4)]
    first = await list_page(client, admin_headers, limit=2)
    await insert_message(db_session)
    second = await list_page(client, admin_headers, limit=2, cursor=first["next_cursor"])
    seen = [i["id"] for i in first["items"] + second["items"]]
    assert seen == sorted(ids, reverse=True)


async def test_deleted_cursor_row_causes_no_gap(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    ids = sorted([(await insert_message(db_session)).id for _ in range(4)], reverse=True)
    first = await list_page(client, admin_headers, limit=2)
    resp = await client.delete(f"{URL}/{ids[1]}", headers=admin_headers)  # the cursor row
    assert resp.status_code == 204
    second = await list_page(client, admin_headers, limit=2, cursor=first["next_cursor"])
    assert [i["id"] for i in second["items"]] == ids[2:]


@pytest.mark.parametrize("cursor", ["not-a-cursor!", "abc", "x" * 200])
async def test_invalid_cursor_is_422(
    client: AsyncClient, admin_headers: dict[str, str], cursor: str
) -> None:
    resp = await client.get(URL, params={"cursor": cursor}, headers=admin_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_cursor"


async def test_overlong_cursor_is_422(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get(URL, params={"cursor": "x" * 201}, headers=admin_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("limit", ["0", "-1", "51", "abc"])
async def test_invalid_limit_is_422(
    client: AsyncClient, admin_headers: dict[str, str], limit: str
) -> None:
    resp = await client.get(URL, params={"limit": limit}, headers=admin_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


# --- list: filters ------------------------------------------------------------------


async def test_filter_by_status(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    new = await insert_message(db_session)
    read = await insert_message(db_session, status=MessageStatus.READ)
    archived = await insert_message(db_session, status=MessageStatus.ARCHIVED)
    for status, msg in (("new", new), ("read", read), ("archived", archived)):
        assert await walk(client, admin_headers, status=status) == [msg.id]


async def test_filter_by_type(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    await insert_message(db_session, type=MessageType.OTHER)
    wanted = await insert_message(db_session, type=MessageType.SUGGESTION)
    assert await walk(client, admin_headers, type="suggestion") == [wanted.id]


async def test_filters_combine_and_page(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    wanted = [
        (await insert_message(db_session, status=MessageStatus.READ, type=MessageType.REQUEST)).id
        for _ in range(5)
    ]
    await insert_message(db_session, status=MessageStatus.NEW, type=MessageType.REQUEST)
    await insert_message(db_session, status=MessageStatus.READ, type=MessageType.OTHER)
    result = await walk(client, admin_headers, status="read", type="request", limit=2)
    assert result == sorted(wanted, reverse=True)


@pytest.mark.parametrize("params", [{"status": "deleted"}, {"type": "spam"}, {"status": "NEW"}])
async def test_invalid_filter_is_422(
    client: AsyncClient, admin_headers: dict[str, str], params: dict[str, str]
) -> None:
    resp = await client.get(URL, params=params, headers=admin_headers)
    assert resp.status_code == 422


# --- stats --------------------------------------------------------------------------


async def test_stats(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    for status, count in ((MessageStatus.NEW, 3), (MessageStatus.READ, 2)):
        for _ in range(count):
            await insert_message(db_session, status=status)
    resp = await client.get(STATS, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == {"new": 3, "read": 2, "archived": 0}


async def test_stats_empty(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get(STATS, headers=admin_headers)
    assert resp.json() == {"new": 0, "read": 0, "archived": 0}


# --- detail -------------------------------------------------------------------------


async def test_detail_returns_full_message_without_internal_fields(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    content = "x" * 400
    msg = await insert_message(
        db_session, content=content, locale=Locale.AR, user_agent="Agent/1.0"
    )
    resp = await client.get(f"{URL}/{msg.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == {
        "id",
        "name",
        "email",
        "type",
        "content",
        "locale",
        "status",
        "user_agent",
        "created_at",
        "read_at",
    }
    assert data["content"] == content
    assert data["locale"] == "ar"
    assert data["user_agent"] == "Agent/1.0"
    assert msg.ip_hash is not None and msg.ip_hash not in resp.text
    assert msg.content_hash not in resp.text


async def test_detail_get_does_not_mark_read(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    msg = await insert_message(db_session)
    await client.get(f"{URL}/{msg.id}", headers=admin_headers)
    assert await db_row(db_session, msg.id) == (MessageStatus.NEW, None)


@pytest.mark.parametrize("method", ["GET", "DELETE"])
async def test_missing_message_is_404(
    client: AsyncClient, admin_headers: dict[str, str], method: str
) -> None:
    resp = await client.request(method, f"{URL}/999999", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json() == NOT_FOUND


async def test_patch_missing_message_is_404(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    resp = await client.patch(f"{URL}/999999", json={"status": "read"}, headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json() == NOT_FOUND


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1", "99999999999999999999"])
@pytest.mark.parametrize("method", ["GET", "DELETE"])
async def test_invalid_id_is_422_not_500(
    client: AsyncClient, admin_headers: dict[str, str], method: str, bad_id: str
) -> None:
    resp = await client.request(method, f"{URL}/{bad_id}", headers=admin_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


# --- status changes -----------------------------------------------------------------


@pytest.mark.parametrize("target", ["read", "archived"])
async def test_leaving_new_sets_read_at(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str], target: str
) -> None:
    msg = await insert_message(db_session)
    resp = await client.patch(f"{URL}/{msg.id}", json={"status": target}, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == target
    assert data["read_at"] is not None
    assert "content" in data  # returns the full updated message
    row = await db_row(db_session, msg.id)
    assert row is not None
    assert row.status == MessageStatus(target)
    assert row.read_at is not None


async def test_setting_new_on_new_leaves_read_at_empty(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    msg = await insert_message(db_session)
    resp = await client.patch(f"{URL}/{msg.id}", json={"status": "new"}, headers=admin_headers)
    assert resp.json()["read_at"] is None


@pytest.mark.parametrize("target", ["new", "read", "archived"])
async def test_read_at_keeps_first_value(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str], target: str
) -> None:
    msg = await insert_message(db_session, status=MessageStatus.READ, read_at=OLD_READ_AT)
    resp = await client.patch(f"{URL}/{msg.id}", json={"status": target}, headers=admin_headers)
    assert resp.status_code == 200
    assert await db_row(db_session, msg.id) == (MessageStatus(target), OLD_READ_AT)


async def test_mark_unread_then_read_keeps_first_read_at(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    msg = await insert_message(db_session, status=MessageStatus.READ, read_at=OLD_READ_AT)
    url = f"{URL}/{msg.id}"
    await client.patch(url, json={"status": "new"}, headers=admin_headers)
    await client.patch(url, json={"status": "read"}, headers=admin_headers)
    assert await db_row(db_session, msg.id) == (MessageStatus.READ, OLD_READ_AT)


@pytest.mark.parametrize(
    "payload",
    [{}, {"status": "deleted"}, {"status": "READ"}, {"status": None}, {"status": "read", "x": 1}],
    ids=["empty", "unknown", "uppercase", "null", "extra-field"],
)
async def test_invalid_patch_is_422_and_changes_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
    payload: dict[str, Any],
) -> None:
    msg = await insert_message(db_session)
    resp = await client.patch(f"{URL}/{msg.id}", json=payload, headers=admin_headers)
    assert resp.status_code == 422
    assert await db_row(db_session, msg.id) == (MessageStatus.NEW, None)


# --- delete -------------------------------------------------------------------------


async def test_delete(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    doomed = await insert_message(db_session)
    kept = await insert_message(db_session)
    url = f"{URL}/{doomed.id}"

    resp = await client.delete(url, headers=admin_headers)
    assert resp.status_code == 204
    assert resp.content == b""

    assert await db_row(db_session, doomed.id) is None
    assert await db_row(db_session, kept.id) is not None
    assert (await client.get(url, headers=admin_headers)).status_code == 404
    assert (await client.delete(url, headers=admin_headers)).status_code == 404
