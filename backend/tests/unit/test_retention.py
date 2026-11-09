from datetime import timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.models.admin_login_attempt import AdminLoginAttempt
from app.models.admin_session import AdminSession
from app.models.admin_user import AdminUser
from app.models.contact_message import ContactMessage
from app.services.retention_service import PurgeResult, purge_old_data
from tests.factories import hex64, insert_message

DAY = timedelta(days=1)


async def client_data(db: AsyncSession, message_id: int) -> tuple[str | None, str | None]:
    stmt = sa.select(ContactMessage.ip_hash, ContactMessage.user_agent).where(
        ContactMessage.id == message_id
    )
    ip_hash, user_agent = (await db.execute(stmt)).one()
    return ip_hash, user_agent


async def test_blanks_client_data_only_on_old_messages(db_session: AsyncSession) -> None:
    old = await insert_message(db_session, age=91 * DAY, user_agent="Old/1.0")
    recent = await insert_message(db_session, age=89 * DAY, user_agent="Recent/1.0")

    result = await purge_old_data(db_session, days=90)

    assert result.messages_blanked == 1
    assert await client_data(db_session, old.id) == (None, None)
    ip_hash, user_agent = await client_data(db_session, recent.id)
    assert ip_hash is not None
    assert user_agent == "Recent/1.0"


async def test_keeps_the_message_itself(db_session: AsyncSession) -> None:
    old = await insert_message(db_session, age=200 * DAY, content="Keep this message text")
    await purge_old_data(db_session, days=90)
    stmt = sa.select(ContactMessage.content, ContactMessage.email).where(
        ContactMessage.id == old.id
    )
    content, email = (await db_session.execute(stmt)).one()
    assert content == "Keep this message text"
    assert email


async def test_is_idempotent(db_session: AsyncSession) -> None:
    await insert_message(db_session, age=91 * DAY, user_agent="Old/1.0")
    assert (await purge_old_data(db_session, days=90)).messages_blanked == 1
    assert (await purge_old_data(db_session, days=90)).messages_blanked == 0


async def test_old_message_with_only_a_user_agent_is_blanked(db_session: AsyncSession) -> None:
    old = await insert_message(db_session, age=91 * DAY, ip_hash=None, user_agent="Old/1.0")
    assert (await purge_old_data(db_session, days=90)).messages_blanked == 1
    assert await client_data(db_session, old.id) == (None, None)


async def test_days_is_configurable(db_session: AsyncSession) -> None:
    msg = await insert_message(db_session, age=31 * DAY)
    await purge_old_data(db_session, days=30)
    assert (await client_data(db_session, msg.id))[0] is None


async def test_removes_old_login_attempts(db_session: AsyncSession) -> None:
    now = (await db_session.execute(sa.select(sa.func.now()))).scalar_one()
    db_session.add_all(
        [
            AdminLoginAttempt(ip_hash=hex64("old"), created_at=now - 91 * DAY),
            AdminLoginAttempt(ip_hash=hex64("new"), created_at=now - 89 * DAY),
        ]
    )
    await db_session.flush()
    assert (await purge_old_data(db_session, days=90)).login_attempts_deleted == 1
    left = (await db_session.execute(sa.select(AdminLoginAttempt.ip_hash))).scalars().all()
    assert [value.strip() for value in left] == [hex64("new")]


async def test_removes_only_long_expired_sessions(db_session: AsyncSession) -> None:
    user = AdminUser(email="a@example.com", password_hash="$argon2id$x")
    db_session.add(user)
    await db_session.flush()
    now = (await db_session.execute(sa.select(sa.func.now()))).scalar_one()
    for name, expires in (("old", now - 91 * DAY), ("recent", now - DAY), ("live", now + DAY)):
        db_session.add(
            AdminSession(
                token_hash=hex64(name),
                admin_user_id=user.id,
                created_at=expires - DAY,
                expires_at=expires,
            )
        )
    await db_session.flush()
    assert (await purge_old_data(db_session, days=90)).sessions_deleted == 1
    count = sa.select(sa.func.count()).select_from(AdminSession)
    assert (await db_session.execute(count)).scalar_one() == 2


@pytest.mark.parametrize("days", [0, -1])
async def test_rejects_non_positive_days(db_session: AsyncSession, days: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        await purge_old_data(db_session, days=days)


def test_cli_default_is_90_days(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[int] = []

    async def fake(days: int, database_url: str | None = None) -> PurgeResult:
        seen.append(days)
        return PurgeResult(messages_blanked=3, login_attempts_deleted=2, sessions_deleted=1)

    monkeypatch.setattr(cli, "purge", fake)
    assert cli.main(["purge-old-data"]) == 0
    assert seen == [90]
    output = capsys.readouterr().out
    assert "3" in output and "2" in output and "1" in output


def test_cli_rejects_bad_days(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake(days: int, database_url: str | None = None) -> PurgeResult:
        raise ValueError("days must be at least 1")

    monkeypatch.setattr(cli, "purge", fake)
    assert cli.main(["purge-old-data", "--days", "0"]) == 1
    assert "at least 1" in capsys.readouterr().err
