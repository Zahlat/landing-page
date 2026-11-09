"""Removes visitor metadata that is no longer needed. Run from the CLI (`purge-old-data`)."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.admin_repository import AdminRepository
from app.repositories.message_repository import MessageRepository

logger = logging.getLogger("app.retention")

DEFAULT_RETENTION_DAYS = 90


@dataclass(frozen=True)
class PurgeResult:
    messages_blanked: int
    login_attempts_deleted: int
    sessions_deleted: int


async def purge_old_data(session: AsyncSession, days: int = DEFAULT_RETENTION_DAYS) -> PurgeResult:
    """Blanks ip_hash and user_agent on old messages, and removes old login attempts and
    long-expired sessions. Message text and contact details are kept."""
    if days < 1:
        raise ValueError("days must be at least 1")
    age = timedelta(days=days)
    admin_repo = AdminRepository(session)
    result = PurgeResult(
        messages_blanked=await MessageRepository(session).blank_client_data_older_than(age),
        login_attempts_deleted=await admin_repo.delete_login_attempts_older_than(age),
        sessions_deleted=await admin_repo.delete_sessions_expired_longer_than(age),
    )
    await session.commit()
    logger.info(
        "purge_done messages=%s attempts=%s sessions=%s",
        result.messages_blanked,
        result.login_attempts_deleted,
        result.sessions_deleted,
    )
    return result
