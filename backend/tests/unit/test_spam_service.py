from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.repositories.message_repository import MessageRepository, WindowCount
from app.services.spam_service import (
    RATE_WINDOW,
    SpamService,
    SpamVerdict,
    count_links,
    retry_after_seconds,
)
from tests.factories import hex64, insert_message

IP = hex64("the-ip")
EMAIL = "limit@example.com"


@pytest.fixture
def spam(db_session: AsyncSession, test_settings: Settings) -> SpamService:
    return SpamService(MessageRepository(db_session), test_settings)


# --- link counting (pure) ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("no links here at all", 0),
        ("see https://example.com for more", 1),
        ("HTTP://EXAMPLE.COM and www.example.org", 2),
        ("http://a.io http://b.io https://c.io", 3),
        ("http://a.io http://b.io https://c.io www.d.io", 4),
        ("https://a.io/path?q=1,https://b.io", 1),  # no whitespace -> one token
        ("email me at me@example.com", 0),
        ("زوروا https://example.com/عربي اليوم", 1),
    ],
)
def test_count_links(text: str, expected: int) -> None:
    assert count_links(text) == expected


def test_link_limit_boundary(spam: SpamService) -> None:
    spam.check_links("http://a.io http://b.io http://c.io")  # 3 is allowed
    with pytest.raises(AppError) as exc:
        spam.check_links("http://a.io http://b.io http://c.io http://d.io")
    assert exc.value.status_code == 422
    assert exc.value.code == "too_many_links"


def test_link_limit_from_settings(db_session: AsyncSession, test_settings: Settings) -> None:
    strict = SpamService(
        MessageRepository(db_session), test_settings.model_copy(update={"max_links_per_message": 0})
    )
    with pytest.raises(AppError):
        strict.check_links("one link: https://example.com")


# --- retry-after (pure) -----------------------------------------------------------

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("oldest", "expected"),
    [
        (NOW, 3600),
        (NOW - timedelta(minutes=30), 1800),
        (NOW - timedelta(minutes=59, seconds=59, milliseconds=500), 1),
        (NOW - timedelta(hours=2), 1),  # never below 1
        (None, 1),
    ],
)
def test_retry_after_seconds(oldest: datetime | None, expected: int) -> None:
    assert retry_after_seconds(WindowCount(5, oldest, NOW), RATE_WINDOW) == expected


# --- per-IP limit (DB) ------------------------------------------------------------


async def test_ip_limit_allows_up_to_limit(spam: SpamService, db_session: AsyncSession) -> None:
    for _ in range(4):
        await insert_message(db_session, ip_hash=IP)
    await spam.check_rate_limits(IP, EMAIL)  # 5th would be allowed


async def test_ip_limit_blocks_at_limit(spam: SpamService, db_session: AsyncSession) -> None:
    for _ in range(5):
        await insert_message(db_session, ip_hash=IP)
    with pytest.raises(AppError) as exc:
        await spam.check_rate_limits(IP, EMAIL)
    assert exc.value.status_code == 429
    assert exc.value.code == "rate_limited"
    assert exc.value.headers is not None
    assert 1 <= int(exc.value.headers["Retry-After"]) <= 3600


async def test_ip_limit_ignores_rows_older_than_an_hour(
    spam: SpamService, db_session: AsyncSession
) -> None:
    for _ in range(5):
        await insert_message(db_session, ip_hash=IP, age=timedelta(minutes=61))
    await spam.check_rate_limits(IP, EMAIL)


async def test_ip_limit_other_ip_unaffected(spam: SpamService, db_session: AsyncSession) -> None:
    for _ in range(5):
        await insert_message(db_session, ip_hash=IP)
    await spam.check_rate_limits(hex64("other-ip"), EMAIL)


async def test_retry_after_reflects_oldest_row(spam: SpamService, db_session: AsyncSession) -> None:
    await insert_message(db_session, ip_hash=IP, age=timedelta(minutes=40))
    for _ in range(4):
        await insert_message(db_session, ip_hash=IP, age=timedelta(minutes=5))
    with pytest.raises(AppError) as exc:
        await spam.check_rate_limits(IP, EMAIL)
    assert exc.value.headers is not None
    # Oldest row leaves the window in 20 minutes.
    assert int(exc.value.headers["Retry-After"]) == 20 * 60


async def test_ip_limit_from_settings(db_session: AsyncSession, test_settings: Settings) -> None:
    spam = SpamService(
        MessageRepository(db_session),
        test_settings.model_copy(update={"rate_limit_ip_per_hour": 1}),
    )
    await spam.check_rate_limits(IP, EMAIL)
    await insert_message(db_session, ip_hash=IP)
    with pytest.raises(AppError):
        await spam.check_rate_limits(IP, EMAIL)


# --- per-email limit (DB) ---------------------------------------------------------


async def test_email_limit_boundary(spam: SpamService, db_session: AsyncSession) -> None:
    for i in range(2):
        await insert_message(db_session, email=EMAIL, ip_hash=hex64(f"ip{i}"))
    await spam.check_rate_limits(IP, EMAIL)  # 3rd allowed
    await insert_message(db_session, email=EMAIL, ip_hash=hex64("ip2"))
    with pytest.raises(AppError) as exc:
        await spam.check_rate_limits(IP, EMAIL)  # 4th blocked
    assert exc.value.status_code == 429


async def test_email_limit_ignores_old_rows(spam: SpamService, db_session: AsyncSession) -> None:
    for _ in range(3):
        await insert_message(db_session, email=EMAIL, age=timedelta(hours=2))
    await spam.check_rate_limits(IP, EMAIL)


# --- duplicates (DB) --------------------------------------------------------------


async def test_duplicate_within_window(spam: SpamService, db_session: AsyncSession) -> None:
    h = hex64("dup")
    await insert_message(db_session, content_hash=h, age=timedelta(hours=23))
    assert await spam.check_duplicate(h) is SpamVerdict.DUPLICATE


async def test_duplicate_outside_window(spam: SpamService, db_session: AsyncSession) -> None:
    h = hex64("dup")
    await insert_message(db_session, content_hash=h, age=timedelta(hours=25))
    assert await spam.check_duplicate(h) is SpamVerdict.ACCEPT


async def test_no_duplicate(spam: SpamService) -> None:
    assert await spam.check_duplicate(hex64("fresh")) is SpamVerdict.ACCEPT
