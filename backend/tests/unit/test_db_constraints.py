"""The DB enforces the same limits as Pydantic, so a bug or a manual insert can't
store bad data. Uses raw SQL to bypass every Python-side check."""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

HEX = "a" * 64

GOOD: dict[str, Any] = {
    "name": "Sara",
    "email": "sara@example.com",
    "type": "question",
    "content": "Hello there, ten+ chars",
    "locale": "en",
    "ip_hash": HEX,
    "content_hash": HEX,
}

INSERT = text(
    "INSERT INTO contact_messages (name, email, type, content, locale, ip_hash, content_hash) "
    "VALUES (:name, :email, :type, :content, :locale, :ip_hash, :content_hash)"
)


async def test_good_row_inserts_with_defaults(db_session: AsyncSession) -> None:
    await db_session.execute(INSERT, GOOD)
    row = (
        await db_session.execute(text("SELECT status, created_at, read_at FROM contact_messages"))
    ).one()
    assert row.status == "new"
    assert row.created_at is not None
    assert row.read_at is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": " padded "},
        {"email": "Upper@Example.com"},
        {"content": "c" * 9},
        {"content": "c" * 5001},
        {"type": "spam"},
        {"type": "REQUEST"},
        {"locale": "fr"},
        {"ip_hash": "Z" * 64},
        {"content_hash": "short"},
    ],
)
async def test_check_constraints_reject(
    db_session: AsyncSession, overrides: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(INSERT, {**GOOD, **overrides})


@pytest.mark.parametrize("overrides", [{"name": "n" * 101}, {"email": "e" * 255}])
async def test_column_lengths_reject(db_session: AsyncSession, overrides: dict[str, Any]) -> None:
    with pytest.raises(DBAPIError):  # string_data_right_truncation
        async with db_session.begin_nested():
            await db_session.execute(INSERT, {**GOOD, **overrides})


async def test_bad_status_rejected(db_session: AsyncSession) -> None:
    await db_session.execute(INSERT, GOOD)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(text("UPDATE contact_messages SET status = 'deleted'"))


async def test_id_cannot_be_supplied(db_session: AsyncSession) -> None:
    with pytest.raises(DBAPIError):  # GENERATED ALWAYS
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO contact_messages "
                    "(id, name, email, type, content, locale, content_hash) "
                    "VALUES (1, :name, :email, :type, :content, :locale, :content_hash)"
                ),
                {
                    k: GOOD[k]
                    for k in ("name", "email", "type", "content", "locale", "content_hash")
                },
            )
