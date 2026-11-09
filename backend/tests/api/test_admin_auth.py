import hashlib
import logging
from datetime import timedelta
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import Settings
from app.core.security import hash_ip, hash_password, new_session_token
from app.models.admin_login_attempt import AdminLoginAttempt
from app.models.admin_session import AdminSession
from app.models.admin_user import AdminUser
from app.services import auth_service
from tests.route_guards import documented_routes, routes_not_rejected

LOGIN = "/v1/admin/auth/login"
LOGOUT = "/v1/admin/auth/logout"
ME = "/v1/admin/me"

EMAIL = "admin@example.com"
PASSWORD = "correct horse battery staple"
# Hashed once: Argon2 is deliberately slow.
PASSWORD_HASH = hash_password(PASSWORD)

INVALID = {"error": {"code": "invalid_credentials", "message": "Invalid email or password."}}


@pytest.fixture
async def admin(db_session: AsyncSession) -> AdminUser:
    user = AdminUser(email=EMAIL, password_hash=PASSWORD_HASH)
    db_session.add(user)
    await db_session.commit()  # commit (not flush): login paths may roll back
    return user


@pytest.fixture
def headers(internal_headers: dict[str, str]) -> dict[str, str]:
    return {**internal_headers, "X-Client-IP": "203.0.113.5"}


def bearer(internal_headers: dict[str, str], token: str) -> dict[str, str]:
    return {**internal_headers, "Authorization": f"Bearer {token}"}


async def login(
    client: AsyncClient,
    headers: dict[str, str],
    email: str = EMAIL,
    password: str = PASSWORD,
    ip: str | None = None,
) -> Response:
    hdrs = {**headers, "X-Client-IP": ip} if ip else headers
    return await client.post(LOGIN, json={"email": email, "password": password}, headers=hdrs)


async def get_user(db: AsyncSession) -> AdminUser:
    db.expire_all()
    stmt = sa.select(AdminUser).where(AdminUser.email == EMAIL)
    return (await db.execute(stmt)).scalar_one()


async def count_attempts(db: AsyncSession) -> int:
    stmt = sa.select(sa.func.count()).select_from(AdminLoginAttempt)
    return (await db.execute(stmt)).scalar_one()


async def make_session(
    db: AsyncSession, user_id: int, *, offset: timedelta = timedelta(hours=8), **values: Any
) -> str:
    """Insert a session row expiring `offset` from now; returns the raw token."""
    token = new_session_token()
    now = (await db.execute(sa.select(sa.func.now()))).scalar_one()
    db.add(
        AdminSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            admin_user_id=user_id,
            created_at=now + offset - timedelta(hours=9),
            expires_at=now + offset,
            **values,
        )
    )
    await db.commit()
    return token


# --- login: success -----------------------------------------------------------------


@pytest.mark.usefixtures("admin")
async def test_login_success(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    resp = await login(client, headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert set(data) == {"token", "expires_at"}
    assert len(data["token"]) == 43

    row = (await db_session.execute(sa.select(AdminSession))).scalar_one()
    assert row.token_hash == hashlib.sha256(data["token"].encode()).hexdigest()
    assert row.token_hash != data["token"]
    assert row.expires_at - row.created_at == timedelta(hours=8)
    assert row.revoked_at is None

    user = await get_user(db_session)
    assert user.last_login_at is not None
    assert user.failed_login_count == 0

    attempt = (await db_session.execute(sa.select(AdminLoginAttempt))).scalar_one()
    assert attempt.succeeded is True


@pytest.mark.usefixtures("admin")
async def test_login_email_is_case_insensitive(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    assert (await login(client, headers, email="ADMIN@Example.COM")).status_code == 200


async def test_session_hours_from_settings(
    db_session: AsyncSession, admin: AdminUser, test_settings: Settings
) -> None:
    service = auth_service.AuthService(
        db_session, test_settings.model_copy(update={"admin_session_hours": 2})
    )
    await service.login(EMAIL, PASSWORD, "203.0.113.5")
    row = (await db_session.execute(sa.select(AdminSession))).scalar_one()
    assert row.expires_at - row.created_at == timedelta(hours=2)
    assert row.admin_user_id == admin.id


async def test_password_whitespace_is_significant(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    spaced = "  spaced out password  "
    db_session.add(AdminUser(email=EMAIL, password_hash=hash_password(spaced)))
    await db_session.commit()
    assert (await login(client, headers, password=spaced.strip())).status_code == 401
    assert (await login(client, headers, password=spaced)).status_code == 200


# --- login: failures and enumeration ------------------------------------------------


@pytest.mark.usefixtures("admin")
async def test_wrong_password(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    resp = await login(client, headers, password="wrong password here")
    assert resp.status_code == 401
    assert resp.json() == INVALID
    assert (await get_user(db_session)).failed_login_count == 1
    sessions = await db_session.execute(sa.select(sa.func.count()).select_from(AdminSession))
    assert sessions.scalar_one() == 0
    assert await count_attempts(db_session) == 1  # survived the error path


@pytest.mark.usefixtures("admin")
async def test_unknown_email_same_response_as_wrong_password(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    wrong = await login(client, headers, password="wrong password here")
    unknown = await login(client, headers, email="nobody@example.com")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == INVALID
    assert unknown.headers.get("retry-after") == wrong.headers.get("retry-after")


async def test_unknown_email_still_runs_argon2(
    client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real = security.verify_password

    def spy(password_hash: str, password: str) -> bool:
        calls.append(password_hash)
        return real(password_hash, password)

    monkeypatch.setattr(auth_service, "verify_password", spy)
    resp = await login(client, headers, email="nobody@example.com")
    assert resp.status_code == 401
    assert calls == [security.DUMMY_PASSWORD_HASH]


@pytest.mark.parametrize(
    "payload",
    [
        {"email": EMAIL},
        {"password": PASSWORD},
        {"email": "not-an-email", "password": PASSWORD},
        {"email": EMAIL, "password": ""},
        {"email": EMAIL, "password": "p" * 1025},
        {"email": EMAIL, "password": PASSWORD, "remember": True},
    ],
    ids=["no-password", "no-email", "bad-email", "empty-password", "long-password", "extra-field"],
)
async def test_login_invalid_body(
    client: AsyncClient, headers: dict[str, str], payload: dict[str, Any]
) -> None:
    resp = await client.post(LOGIN, json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
    assert PASSWORD not in resp.text


# --- account lockout ----------------------------------------------------------------


@pytest.mark.usefixtures("admin")
async def test_lockout_after_five_failures(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    for i in range(5):
        resp = await login(client, headers, password=f"wrong password {i}")
        assert resp.status_code == 401, f"attempt {i + 1}"

    # Locked now: even the correct password is refused.
    resp = await login(client, headers)
    assert resp.status_code == 401
    assert resp.json() == INVALID
    sessions = await db_session.execute(sa.select(sa.func.count()).select_from(AdminSession))
    assert sessions.scalar_one() == 0


@pytest.mark.usefixtures("admin")
async def test_lock_expires(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    for i in range(5):
        await login(client, headers, password=f"wrong password {i}")

    user = await get_user(db_session)
    assert user.locked_until is not None
    user.locked_until -= timedelta(minutes=16)
    await db_session.commit()

    resp = await login(client, headers)
    assert resp.status_code == 200
    user = await get_user(db_session)
    assert user.locked_until is None
    assert user.failed_login_count == 0


@pytest.mark.usefixtures("admin")
async def test_success_resets_failure_count(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    for i in range(4):
        await login(client, headers, password=f"wrong password {i}")
    assert (await get_user(db_session)).failed_login_count == 4
    assert (await login(client, headers)).status_code == 200
    assert (await get_user(db_session)).failed_login_count == 0

    # Failures must be consecutive: four more still doesn't lock.
    for i in range(4):
        assert (await login(client, headers, password=f"again {i}")).status_code == 401
    assert (await login(client, headers)).status_code == 200


# --- per-IP limit -------------------------------------------------------------------


@pytest.mark.usefixtures("admin")
async def test_ip_limit_tenth_allowed_eleventh_blocked(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    for i in range(9):
        resp = await login(client, headers, email=f"nobody{i}@example.com")
        assert resp.status_code == 401, f"attempt {i + 1}"
    assert (await login(client, headers)).status_code == 200  # 10th, correct password

    # 11th: blocked even with valid credentials.
    resp = await login(client, headers)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "too_many_attempts"
    assert 1 <= int(resp.headers["Retry-After"]) <= 15 * 60
    assert await count_attempts(db_session) == 10  # blocked attempt isn't recorded


@pytest.mark.usefixtures("admin")
async def test_ip_limit_other_ip_unaffected(client: AsyncClient, headers: dict[str, str]) -> None:
    for i in range(10):
        await login(client, headers, email=f"nobody{i}@example.com")
    assert (await login(client, headers)).status_code == 429
    assert (await login(client, headers, ip="203.0.113.6")).status_code == 200


@pytest.mark.usefixtures("admin")
async def test_ip_limit_ignores_old_attempts(
    client: AsyncClient,
    db_session: AsyncSession,
    headers: dict[str, str],
    test_settings: Settings,
) -> None:
    ip_hash = hash_ip("203.0.113.5", test_settings.ip_hash_secret.get_secret_value())
    now = (await db_session.execute(sa.select(sa.func.now()))).scalar_one()
    for _ in range(10):
        db_session.add(AdminLoginAttempt(ip_hash=ip_hash, created_at=now - timedelta(minutes=16)))
    await db_session.commit()
    assert (await login(client, headers)).status_code == 200


# --- sessions: /me ------------------------------------------------------------------


@pytest.mark.usefixtures("admin")
async def test_me_returns_only_email(
    client: AsyncClient, headers: dict[str, str], internal_headers: dict[str, str]
) -> None:
    token = (await login(client, headers)).json()["token"]
    resp = await client.get(ME, headers=bearer(internal_headers, token))
    assert resp.status_code == 200
    assert resp.json() == {"email": EMAIL}


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Bearer", "Bearer ", "Basic abc", "token-without-scheme", f"Bearer {'x' * 300}"],
)
async def test_me_rejects_bad_authorization(
    client: AsyncClient, internal_headers: dict[str, str], authorization: str | None
) -> None:
    hdrs = dict(internal_headers)
    if authorization is not None:
        hdrs["Authorization"] = authorization
    resp = await client.get(ME, headers=hdrs)
    assert resp.status_code == 401
    assert resp.json() == {"error": {"code": "unauthorized", "message": "Unauthorized."}}


async def test_me_rejects_unknown_token(
    client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    resp = await client.get(ME, headers=bearer(internal_headers, new_session_token()))
    assert resp.status_code == 401


async def test_stored_hash_is_not_a_valid_token(
    client: AsyncClient,
    db_session: AsyncSession,
    admin: AdminUser,
    internal_headers: dict[str, str],
) -> None:
    # A leaked DB row must not be usable as a credential.
    token = await make_session(db_session, admin.id)
    stored = hashlib.sha256(token.encode()).hexdigest()
    resp = await client.get(ME, headers=bearer(internal_headers, stored))
    assert resp.status_code == 401


async def test_expired_session_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    admin: AdminUser,
    internal_headers: dict[str, str],
) -> None:
    token = await make_session(db_session, admin.id, offset=timedelta(seconds=-1))
    resp = await client.get(ME, headers=bearer(internal_headers, token))
    assert resp.status_code == 401


async def test_revoked_session_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    admin: AdminUser,
    internal_headers: dict[str, str],
) -> None:
    now = (await db_session.execute(sa.select(sa.func.now()))).scalar_one()
    token = await make_session(db_session, admin.id, revoked_at=now)
    resp = await client.get(ME, headers=bearer(internal_headers, token))
    assert resp.status_code == 401


# --- inactive users -----------------------------------------------------------------


async def test_inactive_user_cannot_log_in(
    client: AsyncClient, db_session: AsyncSession, admin: AdminUser, headers: dict[str, str]
) -> None:
    admin.is_active = False
    await db_session.commit()
    resp = await login(client, headers)
    assert resp.status_code == 401
    assert resp.json() == INVALID


async def test_deactivating_user_kills_existing_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
    admin: AdminUser,
    internal_headers: dict[str, str],
) -> None:
    token = await make_session(db_session, admin.id)
    hdrs = bearer(internal_headers, token)
    assert (await client.get(ME, headers=hdrs)).status_code == 200
    admin.is_active = False
    await db_session.commit()
    assert (await client.get(ME, headers=hdrs)).status_code == 401


# --- logout -------------------------------------------------------------------------


@pytest.mark.usefixtures("admin")
async def test_logout_revokes_session(
    client: AsyncClient,
    db_session: AsyncSession,
    headers: dict[str, str],
    internal_headers: dict[str, str],
) -> None:
    token = (await login(client, headers)).json()["token"]
    hdrs = bearer(internal_headers, token)

    resp = await client.post(LOGOUT, headers=hdrs)
    assert resp.status_code == 204
    assert resp.content == b""

    assert (await client.get(ME, headers=hdrs)).status_code == 401
    assert (await client.post(LOGOUT, headers=hdrs)).status_code == 401

    revoked = await db_session.execute(sa.select(AdminSession.revoked_at))
    assert revoked.scalar_one() is not None


@pytest.mark.usefixtures("admin")
async def test_logout_only_revokes_that_session(
    client: AsyncClient, headers: dict[str, str], internal_headers: dict[str, str]
) -> None:
    first = (await login(client, headers)).json()["token"]
    second = (await login(client, headers)).json()["token"]
    assert first != second
    await client.post(LOGOUT, headers=bearer(internal_headers, first))
    assert (await client.get(ME, headers=bearer(internal_headers, second))).status_code == 200


async def test_logout_requires_session(
    client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    assert (await client.post(LOGOUT, headers=internal_headers)).status_code == 401


# --- internal token / route guards --------------------------------------------------


@pytest.mark.usefixtures("admin")
async def test_valid_session_without_internal_token_rejected(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    token = (await login(client, headers)).json()["token"]
    resp = await client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pytest.mark.usefixtures("admin")
async def test_login_requires_internal_token(client: AsyncClient) -> None:
    resp = await client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 401


async def test_every_admin_route_except_login_requires_session(
    app: FastAPI, client: AsyncClient, internal_headers: dict[str, str]
) -> None:
    """Guard for later phases: a valid internal token alone never opens an admin route."""
    routes = [r for r in documented_routes(app, "/v1/admin") if r != ("POST", LOGIN)]
    # Non-vacuous: fails if route discovery ever stops finding the known routes.
    assert {("POST", LOGOUT), ("GET", ME)} <= set(routes)
    assert await routes_not_rejected(client, routes, internal_headers) == []


# --- no secrets in logs -------------------------------------------------------------


@pytest.mark.usefixtures("admin")
async def test_logs_contain_no_credentials(
    client: AsyncClient,
    headers: dict[str, str],
    internal_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="app"):
        await login(client, headers, password="wrong password here")
        token = (await login(client, headers)).json()["token"]
        await client.post(LOGOUT, headers=bearer(internal_headers, token))
    assert caplog.records, "expected some log output"
    for leaked in (PASSWORD, "wrong password here", EMAIL, token, "203.0.113.5"):
        assert leaked not in caplog.text
