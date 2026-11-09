"""Regression tests for the Phase 8 attack review. Each section names the finding it pins."""

import logging
import threading
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.main import build_v1_router
from app.models.admin_user import AdminUser
from app.models.contact_message import ContactMessage
from app.services import auth_service

MESSAGES = "/v1/messages"
LOGIN = "/v1/admin/auth/login"
PII = "sara.private@example.com secret message text"
EMAIL = "admin@example.com"
PASSWORD = "correct horse battery staple"
PASSWORD_HASH = hash_password(PASSWORD)
_n = 0


def body(**overrides: Any) -> dict[str, Any]:
    global _n
    _n += 1
    values: dict[str, Any] = {
        "name": "Tester",
        "email": f"hardening{_n}@example.com",
        "type": "other",
        "content": f"Hardening message number {_n} here.",
        "locale": "en",
    }
    values.update(overrides)
    return values


async def stored(db: AsyncSession) -> int:
    return (await db.execute(sa.select(sa.func.count()).select_from(ContactMessage))).scalar_one()


# --- #1 visitor data must never reach the logs through an error -----------------------


async def test_unhandled_error_logs_type_but_no_exception_text(
    app: FastAPI, internal_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    router = build_v1_router()

    @router.get("/_leak")
    async def leak() -> None:
        raise RuntimeError(PII)

    app.include_router(router)
    # The default transport re-raises anything that escapes the app. That is the path by
    # which uvicorn would print the full exception text, so this also proves it is contained.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        with caplog.at_level(logging.DEBUG):
            resp = await c.get("/v1/_leak", headers=internal_headers)

    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "internal_error"
    assert PII not in resp.text
    assert "RuntimeError" in caplog.text
    assert PII not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


async def test_database_errors_hide_bound_parameters(
    engine: AsyncEngine, db_session: AsyncSession
) -> None:
    assert engine.sync_engine.hide_parameters is True
    with pytest.raises(DBAPIError) as exc:
        async with db_session.begin_nested():
            await db_session.execute(sa.text("SELECT CAST(:v AS text)"), {"v": f"{PII}\x00"})
    assert PII not in str(exc.value)


# --- #2 one IPv6 connection must not get unlimited rate-limit buckets -----------------


async def test_ipv6_addresses_in_one_64_share_a_bucket(
    client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    for i in range(1, 6):
        hdrs = {**internal_headers, "X-Client-IP": f"2001:db8:aaaa:bbbb::{i:x}"}
        assert (await client.post(MESSAGES, json=body(), headers=hdrs)).status_code == 202
    hdrs = {**internal_headers, "X-Client-IP": "2001:db8:aaaa:bbbb:ffff::9"}
    assert (await client.post(MESSAGES, json=body(), headers=hdrs)).status_code == 429

    other = {**internal_headers, "X-Client-IP": "2001:db8:aaaa:cccc::1"}
    assert (await client.post(MESSAGES, json=body(), headers=other)).status_code == 202


async def test_ipv4_mapped_address_shares_the_ipv4_bucket(
    client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    for _ in range(5):
        hdrs = {**internal_headers, "X-Client-IP": "203.0.113.70"}
        assert (await client.post(MESSAGES, json=body(), headers=hdrs)).status_code == 202
    mapped = {**internal_headers, "X-Client-IP": "::ffff:203.0.113.70"}
    assert (await client.post(MESSAGES, json=body(), headers=mapped)).status_code == 429


# --- #3 password hashing must not stall the event loop --------------------------------


@pytest.mark.parametrize("email", [EMAIL, "nobody@example.com"], ids=["known", "unknown"])
async def test_login_hashes_off_the_event_loop(
    client: AsyncClient,
    db_session: AsyncSession,
    internal_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    email: str,
) -> None:
    db_session.add(AdminUser(email=EMAIL, password_hash=PASSWORD_HASH))
    await db_session.commit()
    threads: list[threading.Thread] = []
    real = verify_password

    def spy(password_hash: str, password: str) -> bool:
        threads.append(threading.current_thread())
        return real(password_hash, password)

    monkeypatch.setattr(auth_service, "verify_password", spy)
    await client.post(
        LOGIN, json={"email": email, "password": "wrong password"}, headers=internal_headers
    )
    assert len(threads) == 1
    assert threads[0] is not threading.main_thread()


# --- #4 characters Postgres can't store are a 422, not a 500 --------------------------


@pytest.mark.parametrize("field", ["name", "content"])
async def test_nul_character_is_rejected(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str], field: str
) -> None:
    payload = body(**{field: "long enough value \x00 with nul"})
    resp = await client.post(MESSAGES, json=payload, headers=internal_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
    assert any(f["loc"][-1] == field for f in resp.json()["error"]["fields"])
    assert await stored(db_session) == 0


async def test_nul_in_email_is_rejected(
    client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    resp = await client.post(
        MESSAGES, json=body(email="a\x00b@example.com"), headers=internal_headers
    )
    assert resp.status_code == 422


# --- #5 a locked account must be indistinguishable from an unknown email --------------


async def test_locked_account_looks_like_unknown_email(
    client: AsyncClient, db_session: AsyncSession, internal_headers: dict[str, str]
) -> None:
    db_session.add(AdminUser(email=EMAIL, password_hash=PASSWORD_HASH))
    await db_session.commit()
    hdrs = {**internal_headers, "X-Client-IP": "203.0.113.80"}
    for i in range(5):
        await client.post(LOGIN, json={"email": EMAIL, "password": f"bad {i}"}, headers=hdrs)

    locked = await client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD}, headers=hdrs)
    unknown = await client.post(
        LOGIN, json={"email": "nobody@example.com", "password": "bad"}, headers=hdrs
    )
    assert locked.status_code == unknown.status_code == 401
    assert locked.json() == unknown.json()
    assert "retry-after" not in locked.headers


# --- #6 / #7 safe configuration -------------------------------------------------------

SETTINGS_ARGS: dict[str, Any] = {
    "database_url": "postgresql+asyncpg://user:hunter2hunter2@localhost/db",
    "test_database_url": "postgresql+asyncpg://user:hunter3hunter3@localhost/db_test",
    "internal_token": "t" * 32,
    "ip_hash_secret": "s" * 32,
}


def test_database_passwords_are_not_in_settings_repr() -> None:
    text = repr(Settings(_env_file=None, **SETTINGS_ARGS))
    assert "hunter2hunter2" not in text
    assert "hunter3hunter3" not in text


def test_database_urls_are_secret_strings() -> None:
    settings = Settings(_env_file=None, **SETTINGS_ARGS)
    assert isinstance(settings.database_url, SecretStr)
    assert isinstance(settings.test_database_url, SecretStr)


def test_environment_defaults_to_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert Settings(_env_file=None, **SETTINGS_ARGS).is_prod is True
