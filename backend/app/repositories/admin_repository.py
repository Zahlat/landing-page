from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_login_attempt import AdminLoginAttempt
from app.models.admin_session import AdminSession
from app.models.admin_user import AdminUser
from app.repositories.common import WindowCount, advisory_lock, db_now


class AdminRepository:
    """SQL only; no business rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def now(self) -> datetime:
        return await db_now(self.session)

    async def lock(self, *keys: str) -> None:
        await advisory_lock(self.session, *keys)

    # --- users ----------------------------------------------------------------

    async def get_user_by_email(self, email: str, *, for_update: bool = False) -> AdminUser | None:
        stmt = sa.select(AdminUser).where(AdminUser.email == email)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_user(self, user: AdminUser) -> AdminUser:
        self.session.add(user)
        await self.session.flush()
        return user

    # --- sessions -------------------------------------------------------------

    async def add_session(self, admin_session: AdminSession) -> AdminSession:
        self.session.add(admin_session)
        await self.session.flush()
        return admin_session

    async def get_valid_session(self, token_hash: str) -> tuple[AdminSession, AdminUser] | None:
        """Session that is not revoked, not expired, and belongs to an active user."""
        stmt = (
            sa.select(AdminSession, AdminUser)
            .join(AdminUser, AdminUser.id == AdminSession.admin_user_id)
            .where(
                AdminSession.token_hash == token_hash,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > sa.func.now(),
                AdminUser.is_active.is_(True),
            )
        )
        row = (await self.session.execute(stmt)).one_or_none()
        return None if row is None else (row[0], row[1])

    async def revoke_session(self, session_id: int) -> None:
        await self.session.execute(
            sa.update(AdminSession)
            .where(AdminSession.id == session_id, AdminSession.revoked_at.is_(None))
            .values(revoked_at=sa.func.now())
        )

    # --- login attempts -------------------------------------------------------

    async def add_login_attempt(self, ip_hash: str) -> AdminLoginAttempt:
        attempt = AdminLoginAttempt(ip_hash=ip_hash, succeeded=False)
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def count_login_attempts_since(self, ip_hash: str, window: timedelta) -> WindowCount:
        # Uses ix_admin_login_attempts_ip_hash_created.
        cutoff = sa.func.now() - sa.literal(window, sa.Interval)
        stmt = sa.select(
            sa.func.count(), sa.func.min(AdminLoginAttempt.created_at), sa.func.now()
        ).where(AdminLoginAttempt.ip_hash == ip_hash, AdminLoginAttempt.created_at > cutoff)
        count, oldest, now = (await self.session.execute(stmt)).one()
        return WindowCount(count=count, oldest=oldest, now=now)

    # --- retention ------------------------------------------------------------

    async def delete_login_attempts_older_than(self, age: timedelta) -> int:
        cutoff = sa.func.now() - sa.literal(age, sa.Interval)
        stmt = (
            sa.delete(AdminLoginAttempt)
            .where(AdminLoginAttempt.created_at < cutoff)
            .returning(AdminLoginAttempt.id)
        )
        return len((await self.session.execute(stmt)).scalars().all())

    async def delete_sessions_expired_longer_than(self, age: timedelta) -> int:
        cutoff = sa.func.now() - sa.literal(age, sa.Interval)
        stmt = (
            sa.delete(AdminSession)
            .where(AdminSession.expires_at < cutoff)
            .returning(AdminSession.id)
        )
        return len((await self.session.execute(stmt)).scalars().all())
