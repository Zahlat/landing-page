from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.contact_message import ContactMessage


@dataclass(frozen=True)
class WindowCount:
    """Rows inside a sliding window, the oldest of them, and the DB's now()."""

    count: int
    oldest: datetime | None
    now: datetime


class MessageRepository:
    """SQL only; no business rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, message: ContactMessage) -> ContactMessage:
        self.session.add(message)
        await self.session.flush()
        return message

    async def lock(self, *keys: str) -> None:
        """Transaction-scoped advisory locks, so two concurrent requests for the same
        IP/email can't both pass a count check. Released on commit/rollback.
        Keys are sorted to keep lock order stable (no deadlocks)."""
        for key in sorted(set(keys)):
            await self.session.execute(
                sa.select(sa.func.pg_advisory_xact_lock(sa.func.hashtextextended(key, 0)))
            )

    async def _count_since(
        self, column: InstrumentedAttribute[Any], value: str, window: timedelta
    ) -> WindowCount:
        cutoff = sa.func.now() - sa.literal(window, sa.Interval)
        stmt = sa.select(
            sa.func.count(),
            sa.func.min(ContactMessage.created_at),
            sa.func.now(),
        ).where(column == value, ContactMessage.created_at > cutoff)
        count, oldest, now = (await self.session.execute(stmt)).one()
        return WindowCount(count=count, oldest=oldest, now=now)

    async def count_by_ip_since(self, ip_hash: str, window: timedelta) -> WindowCount:
        # Uses ix_contact_messages_ip_hash_created.
        return await self._count_since(ContactMessage.ip_hash, ip_hash, window)

    async def count_by_email_since(self, email: str, window: timedelta) -> WindowCount:
        # Uses ix_contact_messages_email_created.
        return await self._count_since(ContactMessage.email, email, window)

    async def exists_content_hash_since(self, content_hash: str, window: timedelta) -> bool:
        # Uses ix_contact_messages_content_hash_created.
        cutoff = sa.func.now() - sa.literal(window, sa.Interval)
        stmt = sa.select(
            sa.exists().where(
                ContactMessage.content_hash == content_hash,
                ContactMessage.created_at > cutoff,
            )
        )
        return bool((await self.session.execute(stmt)).scalar_one())
