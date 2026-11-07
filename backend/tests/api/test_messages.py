from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import content_hash, hash_ip
from app.models.contact_message import ContactMessage
from app.models.enums import Locale, MessageStatus, MessageType

URL = "/v1/messages"


def valid_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Sara",
        "email": "sara@example.com",
        "type": "question",
        "content": "Hello, I have a question about your services.",
        "locale": "en",
    }
    body.update(overrides)
    return body


@pytest.fixture
def headers(internal_headers: dict[str, str]) -> dict[str, str]:
    return {**internal_headers, "X-Client-IP": "203.0.113.7", "X-Client-UA": "pytest-agent/1.0"}


async def count_messages(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(ContactMessage))).scalar_one()


async def only_message(db: AsyncSession) -> ContactMessage:
    return (await db.execute(select(ContactMessage))).scalar_one()


# --- happy path ------------------------------------------------------------------


async def test_valid_message_is_stored(
    client: AsyncClient,
    db_session: AsyncSession,
    headers: dict[str, str],
    test_settings: Settings,
) -> None:
    body = valid_body(name="  Sara Ali  ", email="  Sara.Ali@Example.COM ", locale="ar")
    resp = await client.post(URL, json=body, headers=headers)

    assert resp.status_code == 202
    assert resp.json() == {"status": "received"}

    msg = await only_message(db_session)
    assert msg.name == "Sara Ali"
    assert msg.email == "sara.ali@example.com"
    assert msg.type is MessageType.QUESTION
    assert msg.locale is Locale.AR
    assert msg.status is MessageStatus.NEW
    assert msg.read_at is None
    assert msg.created_at.tzinfo is not None
    assert msg.user_agent == "pytest-agent/1.0"
    secret = test_settings.ip_hash_secret.get_secret_value()
    assert msg.ip_hash == hash_ip("203.0.113.7", secret)
    assert msg.content_hash == content_hash("sara.ali@example.com", body["content"])


async def test_raw_ip_never_stored(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    await client.post(URL, json=valid_body(), headers=headers)
    msg = await only_message(db_session)
    stored = " ".join(str(getattr(msg, c.key)) for c in ContactMessage.__table__.columns)
    assert "203.0.113.7" not in stored


async def test_response_never_exposes_internal_fields(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    resp = await client.post(URL, json=valid_body(), headers=headers)
    assert resp.json() == {"status": "received"}
    for leaked in ("id", "ip_hash", "content_hash", "email", "created_at"):
        assert leaked not in resp.text


@pytest.mark.parametrize("message_type", [t.value for t in MessageType])
async def test_every_message_type_accepted(
    client: AsyncClient, headers: dict[str, str], message_type: str
) -> None:
    resp = await client.post(URL, json=valid_body(type=message_type), headers=headers)
    assert resp.status_code == 202


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "A"},
        {"name": "n" * 100},
        {"content": "c" * 10},
        {"content": "c" * 5000},
        {"content": "ع" * 5000},  # Arabic: 5000 chars, ~10 KB of UTF-8, still under 16 KB
        {"email": f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 57}.com"},  # 254 chars
    ],
    ids=["name-1", "name-100", "content-10", "content-5000", "content-arabic-5000", "email-254"],
)
async def test_boundary_values_accepted(
    client: AsyncClient, headers: dict[str, str], overrides: dict[str, Any]
) -> None:
    if "email" in overrides:
        assert len(overrides["email"]) == 254
    resp = await client.post(URL, json=valid_body(**overrides), headers=headers)
    assert resp.status_code == 202, resp.text


# --- missing / unusual client info -------------------------------------------------


async def test_missing_client_headers_fall_back_to_unknown(
    client: AsyncClient,
    db_session: AsyncSession,
    internal_headers: dict[str, str],
    test_settings: Settings,
) -> None:
    resp = await client.post(URL, json=valid_body(), headers=internal_headers)
    assert resp.status_code == 202
    msg = await only_message(db_session)
    assert msg.ip_hash == hash_ip("unknown", test_settings.ip_hash_secret.get_secret_value())
    assert msg.user_agent is None


async def test_invalid_client_ip_treated_as_unknown(
    client: AsyncClient,
    db_session: AsyncSession,
    internal_headers: dict[str, str],
    test_settings: Settings,
) -> None:
    hdrs = {**internal_headers, "X-Client-IP": "1.2.3.4, 5.6.7.8"}
    await client.post(URL, json=valid_body(), headers=hdrs)
    msg = await only_message(db_session)
    assert msg.ip_hash == hash_ip("unknown", test_settings.ip_hash_secret.get_secret_value())


async def test_user_agent_truncated_to_512(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    hdrs = {**internal_headers, "X-Client-UA": "u" * 2000}
    await client.post(URL, json=valid_body(), headers=hdrs)
    msg = await only_message(db_session)
    assert msg.user_agent == "u" * 512


# --- invalid input ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"name": ""}, "name"),
        ({"name": "    "}, "name"),
        ({"name": "n" * 101}, "name"),
        ({"content": "c" * 9}, "content"),
        ({"content": "   short   "}, "content"),  # 5 chars after trimming
        ({"content": "c" * 5001}, "content"),
        ({"email": "not-an-email"}, "email"),
        ({"email": "a@b"}, "email"),
        ({"email": f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 58}.com"}, "email"),  # 255
        ({"type": "spam"}, "type"),
        ({"type": "Question"}, "type"),
        ({"locale": "fr"}, "locale"),
        ({"locale": "EN"}, "locale"),
        ({"name": 123}, "name"),
    ],
)
async def test_invalid_field_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    headers: dict[str, str],
    overrides: dict[str, Any],
    field: str,
) -> None:
    resp = await client.post(URL, json=valid_body(**overrides), headers=headers)
    assert resp.status_code == 422, resp.text
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    assert any(f["loc"][-1] == field for f in err["fields"])
    assert await count_messages(db_session) == 0


@pytest.mark.parametrize("missing", ["name", "email", "type", "content", "locale"])
async def test_missing_field_rejected(
    client: AsyncClient, headers: dict[str, str], missing: str
) -> None:
    body = valid_body()
    del body[missing]
    resp = await client.post(URL, json=body, headers=headers)
    assert resp.status_code == 422


@pytest.mark.parametrize("extra", [{"status": "read"}, {"id": 1}, {"website": "x"}])
async def test_extra_field_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    headers: dict[str, str],
    extra: dict[str, Any],
) -> None:
    resp = await client.post(URL, json=valid_body(**extra), headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["fields"][0]["type"] == "extra_forbidden"
    assert await count_messages(db_session) == 0


async def test_non_json_body_rejected(client: AsyncClient, headers: dict[str, str]) -> None:
    resp = await client.post(
        URL, content=b"name=x", headers={**headers, "Content-Type": "text/plain"}
    )
    assert resp.status_code == 422


async def test_validation_error_does_not_echo_input(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    resp = await client.post(URL, json=valid_body(email="leak-me-not"), headers=headers)
    assert resp.status_code == 422
    assert "leak-me-not" not in resp.text


# --- size limit ---------------------------------------------------------------------


async def test_body_over_16kb_rejected(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    resp = await client.post(URL, json=valid_body(padding="x" * 17_000), headers=headers)
    assert resp.status_code == 413
    assert resp.json() == {
        "error": {"code": "payload_too_large", "message": "Request body too large."}
    }
    assert await count_messages(db_session) == 0


async def test_chunked_body_over_16kb_rejected(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    async def chunks() -> Any:
        for _ in range(20):
            yield b"x" * 1024

    # An async iterator body is sent without Content-Length.
    resp = await client.post(
        URL, content=chunks(), headers={**headers, "Content-Type": "application/json"}
    )
    assert resp.status_code == 413


async def test_body_just_under_limit_reaches_validation(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    resp = await client.post(URL, json=valid_body(padding="x" * 15_000), headers=headers)
    assert resp.status_code == 422  # not 413: it got past the size cap


# --- auth ---------------------------------------------------------------------------


async def test_requires_internal_token(client: AsyncClient, db_session: AsyncSession) -> None:
    resp = await client.post(URL, json=valid_body(), headers={"X-Client-IP": "203.0.113.7"})
    assert resp.status_code == 401
    assert await count_messages(db_session) == 0


async def test_get_not_allowed(client: AsyncClient, headers: dict[str, str]) -> None:
    resp = await client.get(URL, headers=headers)
    assert resp.status_code == 405
    assert resp.json()["error"]["code"] == "method_not_allowed"
