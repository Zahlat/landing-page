"""SQL helpers shared by repositories."""

from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class WindowCount:
    """Rows inside a sliding window, the oldest of them, and the DB's now()."""

    count: int
    oldest: datetime | None
    now: datetime


async def advisory_lock(session: AsyncSession, *keys: str) -> None:
    """Transaction-scoped advisory locks, so concurrent requests for the same key can't
    both pass a count check. Released on commit/rollback. Keys are sorted to keep lock
    order stable (no deadlocks)."""
    for key in sorted(set(keys)):
        await session.execute(
            sa.select(sa.func.pg_advisory_xact_lock(sa.func.hashtextextended(key, 0)))
        )


async def db_now(session: AsyncSession) -> datetime:
    """The database's now() (transaction start time), so all comparisons use one clock."""
    value: datetime = (await session.execute(sa.select(sa.func.now()))).scalar_one()
    return value
