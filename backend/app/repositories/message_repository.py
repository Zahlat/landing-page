from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.pagination import Cursor
from app.models.contact_message import PREVIEW_CHARS, ContactMessage
from app.models.enums import MessageStatus, MessageType
from app.repositories.common import WindowCount, advisory_lock, db_now

__all__ = ["MessageRepository", "WindowCount"]


class MessageRepository:
    """SQL only; no business rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, message: ContactMessage) -> ContactMessage:
        self.session.add(message)
        await self.session.flush()
        return message

    async def lock(self, *keys: str) -> None:
        await advisory_lock(self.session, *keys)

    async def now(self) -> datetime:
        return await db_now(self.session)

    # --- admin ----------------------------------------------------------------

    async def list_page(
        self,
        *,
        status: MessageStatus | None,
        message_type: MessageType | None,
        cursor: Cursor | None,
        limit: int,
    ) -> Sequence[sa.Row[Any]]:
        """Up to `limit` rows, newest first, after the cursor. Keyset, never OFFSET.
        Selects only a preview, so full message text never loads for the list."""
        stmt = sa.select(
            ContactMessage.id,
            ContactMessage.created_at,
            ContactMessage.name,
            ContactMessage.email,
            ContactMessage.type,
            ContactMessage.status,
            sa.func.left(ContactMessage.content, PREVIEW_CHARS).label("preview"),
        )
        if status is not None:
            stmt = stmt.where(ContactMessage.status == status)
        if message_type is not None:
            stmt = stmt.where(ContactMessage.type == message_type)
        if cursor is not None:
            stmt = stmt.where(
                sa.tuple_(ContactMessage.created_at, ContactMessage.id)
                < sa.tuple_(
                    sa.literal(cursor.created_at, sa.DateTime(timezone=True)),
                    sa.literal(cursor.id, sa.BigInteger),
                )
            )
        stmt = stmt.order_by(ContactMessage.created_at.desc(), ContactMessage.id.desc())
        return (await self.session.execute(stmt.limit(limit))).all()

    async def status_counts(self) -> dict[MessageStatus, int]:
        stmt = sa.select(ContactMessage.status, sa.func.count()).group_by(ContactMessage.status)
        return {status: count for status, count in (await self.session.execute(stmt)).all()}

    async def get(self, message_id: int, *, for_update: bool = False) -> ContactMessage | None:
        stmt = sa.select(ContactMessage).where(ContactMessage.id == message_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def blank_client_data_older_than(self, age: timedelta) -> int:
        """Clears ip_hash and user_agent; the message itself is kept."""
        cutoff = sa.func.now() - sa.literal(age, sa.Interval)
        stmt = (
            sa.update(ContactMessage)
            .where(
                ContactMessage.created_at < cutoff,
                sa.or_(ContactMessage.ip_hash.is_not(None), ContactMessage.user_agent.is_not(None)),
            )
            .values(ip_hash=None, user_agent=None)
            .returning(ContactMessage.id)
            .execution_options(synchronize_session=False)
        )
        return len((await self.session.execute(stmt)).scalars().all())

    async def delete(self, message_id: int) -> bool:
        stmt = (
            sa.delete(ContactMessage)
            .where(ContactMessage.id == message_id)
            .returning(ContactMessage.id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

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
