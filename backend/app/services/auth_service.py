"""Admin login, lockout and sessions.

Login order:
1. Per-IP limit (any outcome counts) -> 429. A blocked attempt is not recorded.
2. Record the attempt.
3. Load the user FOR UPDATE (serializes concurrent logins for one account).
4. Unknown email / inactive user -> verify against a dummy hash, 401.
5. Locked account -> verify against a dummy hash, the same 401 as a wrong password.
6. Wrong password -> failed_login_count += 1; at the limit, lock and reset; 401.
7. Success -> reset counters, set last_login_at, create session, 200.

Failures commit *before* raising: the request's session is rolled back on error,
which would otherwise discard the attempt row and the failure counter.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_ip,
    hash_password,
    hash_token,
    new_session_token,
    password_needs_rehash,
    run_argon2,
    verify_password,
)
from app.models.admin_session import AdminSession
from app.models.admin_user import AdminUser
from app.repositories.admin_repository import AdminRepository
from app.services.limits import retry_after_seconds

logger = logging.getLogger("app.auth")

MIN_PASSWORD_LENGTH = 12


def _invalid_credentials() -> AppError:
    # One message for unknown email, inactive user and wrong password.
    return AppError(401, "invalid_credentials", "Invalid email or password.")


def _unauthorized() -> AppError:
    return AppError(401, "unauthorized", "Unauthorized.")


@dataclass(frozen=True)
class LoginResult:
    token: str  # raw token: returned once, never stored
    expires_at: datetime


@dataclass(frozen=True)
class AdminContext:
    user: AdminUser
    session: AdminSession


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repo = AdminRepository(session)

    # --- login ----------------------------------------------------------------

    async def login(self, email: str, password: str, client_ip: str) -> LoginResult:
        s = self.settings
        ip_hash = hash_ip(client_ip, s.ip_hash_secret.get_secret_value())
        await self.repo.lock(f"login:ip:{ip_hash}")

        window = timedelta(minutes=s.login_ip_window_minutes)
        attempts = await self.repo.count_login_attempts_since(ip_hash, window)
        if attempts.count >= s.login_ip_max_attempts:
            await self.session.rollback()
            logger.warning("login_ip_limited")
            raise AppError(
                429,
                "too_many_attempts",
                "Too many login attempts. Please try again later.",
                headers={"Retry-After": str(retry_after_seconds(attempts, window))},
            )

        attempt = await self.repo.add_login_attempt(ip_hash)
        user = await self.repo.get_user_by_email(email, for_update=True)

        if user is None or not user.is_active:
            await run_argon2(verify_password, DUMMY_PASSWORD_HASH, password)  # equalize timing
            await self.session.commit()
            logger.info("login_failed reason=unknown_or_inactive")
            raise _invalid_credentials()

        now = await self.repo.now()
        if user.locked_until is not None and user.locked_until > now:
            await run_argon2(verify_password, DUMMY_PASSWORD_HASH, password)
            await self.session.commit()
            logger.info("login_blocked_locked user_id=%s", user.id)
            # Same answer as a wrong password: a distinct response would confirm the email exists.
            raise _invalid_credentials()

        if not await run_argon2(verify_password, user.password_hash, password):
            user.failed_login_count += 1
            if user.failed_login_count >= s.login_max_failures:
                user.locked_until = now + timedelta(minutes=s.login_lockout_minutes)
                user.failed_login_count = 0
                logger.warning("login_account_locked user_id=%s", user.id)
            await self.session.commit()
            logger.info("login_failed reason=bad_password user_id=%s", user.id)
            raise _invalid_credentials()

        # Success.
        if password_needs_rehash(user.password_hash):
            user.password_hash = await run_argon2(hash_password, password)
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        attempt.succeeded = True

        token = new_session_token()
        expires_at = now + timedelta(hours=s.admin_session_hours)
        await self.repo.add_session(
            AdminSession(
                token_hash=hash_token(token),
                admin_user_id=user.id,
                created_at=now,
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        logger.info("login_ok user_id=%s", user.id)
        return LoginResult(token=token, expires_at=expires_at)

    # --- sessions -------------------------------------------------------------

    async def authenticate(self, token: str) -> AdminContext:
        found = await self.repo.get_valid_session(hash_token(token))
        if found is None:
            raise _unauthorized()
        admin_session, user = found
        return AdminContext(user=user, session=admin_session)

    async def logout(self, ctx: AdminContext) -> None:
        await self.repo.revoke_session(ctx.session.id)
        await self.session.commit()
        logger.info("logout user_id=%s", ctx.user.id)

    # --- admin management (CLI) -----------------------------------------------

    async def create_admin(self, email: str, password: str) -> AdminUser:
        email = email.strip().lower()
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if await self.repo.get_user_by_email(email) is not None:
            raise ValueError("An admin with that email already exists.")
        password_hash = await run_argon2(hash_password, password)
        user = await self.repo.add_user(AdminUser(email=email, password_hash=password_hash))
        await self.session.commit()
        return user
