from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.main import create_app
from app.models.contact_message import ContactMessage

URL = "/v1/messages"
_n = 0


def body(**overrides: Any) -> dict[str, Any]:
    """A valid message with unique email + content, so only the rule under test fires."""
    global _n
    _n += 1
    b: dict[str, Any] = {
        "name": "Tester",
        "email": f"user{_n}@example.com",
        "type": "request",
        "content": f"Message number {_n} about a project.",
        "locale": "en",
    }
    b.update(overrides)
    return b


def from_ip(internal_headers: dict[str, str], ip: str) -> dict[str, str]:
    return {**internal_headers, "X-Client-IP": ip}


async def stored(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(ContactMessage))).scalar_one()


def assert_rate_limited(resp: Response) -> None:
    assert resp.status_code == 429, resp.text
    assert resp.json() == {
        "error": {"code": "rate_limited", "message": "Too many messages. Please try again later."}
    }
    retry = int(resp.headers["Retry-After"])
    assert 1 <= retry <= 3600


# --- per-IP -------------------------------------------------------------------------


async def test_ip_limit_fifth_allowed_sixth_blocked(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    hdrs = from_ip(internal_headers, "203.0.113.10")
    for i in range(5):
        resp = await client.post(URL, json=body(), headers=hdrs)
        assert resp.status_code == 202, f"message {i + 1}: {resp.text}"

    assert_rate_limited(await client.post(URL, json=body(), headers=hdrs))
    assert await stored(db_session) == 5  # the 6th was not stored


async def test_ip_limit_does_not_affect_other_ip(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    blocked = from_ip(internal_headers, "203.0.113.10")
    for _ in range(5):
        await client.post(URL, json=body(), headers=blocked)
    assert_rate_limited(await client.post(URL, json=body(), headers=blocked))

    other = await client.post(URL, json=body(), headers=from_ip(internal_headers, "203.0.113.11"))
    assert other.status_code == 202
    assert await stored(db_session) == 6


async def test_ip_variants_share_one_bucket(
    client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    # Different spellings of the same IPv6 address normalize to one bucket.
    spellings = [
        "2001:db8::1",
        "2001:DB8::1",
        "2001:db8:0:0:0:0:0:1",
        " 2001:db8::1 ",
        "2001:db8::01",
    ]
    for ip in spellings:
        assert (
            await client.post(URL, json=body(), headers=from_ip(internal_headers, ip))
        ).status_code == 202
    assert_rate_limited(
        await client.post(URL, json=body(), headers=from_ip(internal_headers, "2001:0db8::1"))
    )


async def test_missing_ip_still_rate_limited(
    client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    for _ in range(5):
        assert (await client.post(URL, json=body(), headers=internal_headers)).status_code == 202
    assert_rate_limited(await client.post(URL, json=body(), headers=internal_headers))


# --- per-email ----------------------------------------------------------------------


async def test_email_limit_third_allowed_fourth_blocked(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    for i in range(3):
        resp = await client.post(
            URL,
            json=body(email="same@example.com"),
            headers=from_ip(internal_headers, f"198.51.100.{i + 1}"),
        )
        assert resp.status_code == 202, resp.text

    # Different IP and different casing: still the same (lowercased) email.
    resp = await client.post(
        URL, json=body(email="SAME@Example.com"), headers=from_ip(internal_headers, "198.51.100.99")
    )
    assert_rate_limited(resp)
    assert await stored(db_session) == 3


# --- links --------------------------------------------------------------------------


async def test_three_links_allowed(client: AsyncClient, internal_headers: dict[str, str]) -> None:
    content = "See https://a.example http://b.example and www.c.example please"
    resp = await client.post(URL, json=body(content=content), headers=internal_headers)
    assert resp.status_code == 202


async def test_four_links_rejected(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    content = "https://a.example https://b.example https://c.example https://d.example"
    resp = await client.post(URL, json=body(content=content), headers=internal_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "too_many_links"
    assert await stored(db_session) == 0


async def test_link_rejection_does_not_consume_rate_limit(
    client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    hdrs = from_ip(internal_headers, "203.0.113.20")
    spam_links = "https://a.example https://b.example https://c.example https://d.example"
    for _ in range(6):
        await client.post(URL, json=body(content=spam_links), headers=hdrs)
    assert (await client.post(URL, json=body(), headers=hdrs)).status_code == 202


# --- duplicates ---------------------------------------------------------------------


async def test_duplicate_gets_fake_202_and_is_not_stored(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    msg = body()
    first = await client.post(URL, json=msg, headers=internal_headers)
    second = await client.post(URL, json=msg, headers=internal_headers)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json() == {"status": "received"}
    assert await stored(db_session) == 1


async def test_duplicate_detection_normalizes(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    await client.post(
        URL,
        json=body(email="dup@example.com", content="Hello there friend"),
        headers=internal_headers,
    )
    resp = await client.post(
        URL,
        json=body(email="DUP@example.com", content="  hello   THERE\nfriend "),
        headers=from_ip(internal_headers, "203.0.113.50"),  # different IP doesn't matter
    )
    assert resp.status_code == 202
    assert await stored(db_session) == 1


async def test_same_content_different_email_is_not_duplicate(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    content = "Exactly the same text in both messages."
    await client.post(URL, json=body(content=content), headers=internal_headers)
    await client.post(URL, json=body(content=content), headers=internal_headers)
    assert await stored(db_session) == 2


# --- limits come from settings ------------------------------------------------------


@pytest.fixture
async def strict_client(
    db_session: AsyncSession, test_settings: Settings
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        test_settings.model_copy(
            update={"rate_limit_ip_per_hour": 2, "rate_limit_email_per_hour": 10}
        )
    )

    async def _db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_ip_limit_read_from_settings(
    strict_client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    hdrs = from_ip(internal_headers, "203.0.113.30")
    for _ in range(2):
        assert (await strict_client.post(URL, json=body(), headers=hdrs)).status_code == 202
    assert_rate_limited(await strict_client.post(URL, json=body(), headers=hdrs))
