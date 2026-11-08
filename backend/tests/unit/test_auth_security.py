from datetime import timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.core.config import Settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    hash_token,
    new_session_token,
    password_needs_rehash,
    verify_password,
)
from app.models.admin_session import AdminSession
from app.models.admin_user import AdminUser
from app.services.auth_service import AuthService

HASH = hash_password("a long enough password")
HEX = "a" * 64

# --- password + token helpers -------------------------------------------------------


def test_password_hash_is_argon2id() -> None:
    assert HASH.startswith("$argon2id$")
    assert "a long enough password" not in HASH
    assert not password_needs_rehash(HASH)


def test_verify_password() -> None:
    assert verify_password(HASH, "a long enough password") is True
    assert verify_password(HASH, "a long enough passworD") is False
    assert verify_password(HASH, "") is False


@pytest.mark.parametrize("bad", ["", "not-a-hash", "$argon2id$broken"])
def test_verify_password_bad_hash_is_false_not_error(bad: str) -> None:
    assert verify_password(bad, "whatever") is False


def test_dummy_hash_is_a_real_argon2id_hash() -> None:
    assert DUMMY_PASSWORD_HASH.startswith("$argon2id$")
    assert verify_password(DUMMY_PASSWORD_HASH, "guess") is False


def test_session_tokens() -> None:
    a, b = new_session_token(), new_session_token()
    assert a != b
    assert len(a) == 43
    assert len(hash_token(a)) == 64
    assert hash_token(a) == hash_token(a) != hash_token(b)


# --- create-admin -------------------------------------------------------------------


@pytest.fixture
def service(db_session: AsyncSession, test_settings: Settings) -> AuthService:
    return AuthService(db_session, test_settings)


async def test_create_admin(service: AuthService, db_session: AsyncSession) -> None:
    user = await service.create_admin("  New.Admin@Example.COM ", "a long enough password")
    assert user.email == "new.admin@example.com"
    assert user.is_active is True
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(user.password_hash, "a long enough password")
    stored = await db_session.execute(sa.select(sa.func.count()).select_from(AdminUser))
    assert stored.scalar_one() == 1


async def test_create_admin_duplicate_email(service: AuthService) -> None:
    await service.create_admin("a@example.com", "a long enough password")
    with pytest.raises(ValueError, match="already exists"):
        await service.create_admin("A@EXAMPLE.com", "another long password")


async def test_create_admin_short_password(service: AuthService) -> None:
    with pytest.raises(ValueError, match="at least 12"):
        await service.create_admin("a@example.com", "short")


def test_prompt_password_must_match() -> None:
    answers = iter(["first password!", "other password!"])
    with pytest.raises(ValueError, match="do not match"):
        cli.prompt_password(lambda _: next(answers))


def test_prompt_password_returns_password() -> None:
    assert cli.prompt_password(lambda _: "same password!") == "same password!"


def test_cli_refuses_password_argument() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["create-admin", "--email", "a@example.com", "--password", "hunter2hunter2"])
    assert exc.value.code == 2


def test_cli_never_prints_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_create(email: str, password: str, database_url: str | None = None) -> str:
        assert password == "a long enough password"
        return email

    monkeypatch.setattr(cli, "prompt_password", lambda: "a long enough password")
    monkeypatch.setattr(cli, "create_admin", fake_create)
    # asyncio.run() can't nest inside pytest-asyncio's loop only when a loop is running;
    # this sync test runs outside it.
    assert cli.main(["create-admin", "--email", "a@example.com"]) == 0
    captured = capsys.readouterr()
    assert "a long enough password" not in captured.out + captured.err


def test_cli_reports_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def bad_prompt() -> str:
        raise ValueError("Passwords do not match.")

    monkeypatch.setattr(cli, "prompt_password", bad_prompt)
    assert cli.main(["create-admin", "--email", "a@example.com"]) == 1
    assert "do not match" in capsys.readouterr().err


# --- DB constraints -----------------------------------------------------------------


async def _user(db: AsyncSession) -> AdminUser:
    user = AdminUser(email="c@example.com", password_hash=HASH)
    db.add(user)
    await db.flush()
    return user


@pytest.mark.parametrize(
    "values",
    [
        {"email": "Upper@Example.com", "password_hash": HASH},
        {"email": "c@example.com", "password_hash": "plaintext"},
        {"email": "c@example.com", "password_hash": HASH, "failed_login_count": -1},
    ],
    ids=["uppercase-email", "non-argon2-hash", "negative-failures"],
)
async def test_admin_user_constraints(db_session: AsyncSession, values: dict[str, object]) -> None:
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(sa.insert(AdminUser).values(**values))


async def test_admin_email_unique(db_session: AsyncSession) -> None:
    await _user(db_session)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                sa.insert(AdminUser).values(email="c@example.com", password_hash=HASH)
            )


async def test_session_expiry_must_follow_creation(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    now = (await db_session.execute(sa.select(sa.func.now()))).scalar_one()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                sa.insert(AdminSession).values(
                    token_hash=HEX, admin_user_id=user.id, created_at=now, expires_at=now
                )
            )


async def test_session_token_hash_must_be_hex(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    now = (await db_session.execute(sa.select(sa.func.now()))).scalar_one()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                sa.insert(AdminSession).values(
                    token_hash="raw-token-not-a-hash",
                    admin_user_id=user.id,
                    expires_at=now + timedelta(hours=1),
                )
            )


async def test_deleting_user_cascades_to_sessions(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    now = (await db_session.execute(sa.select(sa.func.now()))).scalar_one()
    await db_session.execute(
        sa.insert(AdminSession).values(
            token_hash=HEX, admin_user_id=user.id, expires_at=now + timedelta(hours=1)
        )
    )
    await db_session.execute(sa.delete(AdminUser).where(AdminUser.id == user.id))
    remaining = await db_session.execute(sa.select(sa.func.count()).select_from(AdminSession))
    assert remaining.scalar_one() == 0
