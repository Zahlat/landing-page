import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import content_hash, hash_ip
from app.models.contact_message import USER_AGENT_MAX, ContactMessage
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate
from app.services.spam_service import SpamService, SpamVerdict

logger = logging.getLogger("app.messages")


@dataclass(frozen=True)
class ClientInfo:
    ip: str  # normalized IP or "unknown"; never persisted raw
    user_agent: str | None


class MessageService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repo = MessageRepository(session)
        self.spam = SpamService(self.repo, settings)

    async def submit(self, data: MessageCreate, client: ClientInfo) -> None:
        """Store the message, or raise AppError (422/429).

        Returns normally for duplicates too, without storing: the client sees the
        same 202 either way, so a bot can't learn that it was filtered.
        """
        self.spam.check_links(data.content)

        ip_hash = hash_ip(client.ip, self.settings.ip_hash_secret.get_secret_value())
        c_hash = content_hash(data.email, data.content)

        await self.spam.check_rate_limits(ip_hash, data.email)

        if await self.spam.check_duplicate(c_hash) is SpamVerdict.DUPLICATE:
            await self.session.rollback()  # release the advisory locks
            logger.info("message_duplicate_dropped type=%s locale=%s", data.type, data.locale)
            return

        message = ContactMessage(
            name=data.name,
            email=data.email,
            type=data.type,
            content=data.content,
            locale=data.locale,
            ip_hash=ip_hash,
            content_hash=c_hash,
            user_agent=client.user_agent[:USER_AGENT_MAX] if client.user_agent else None,
        )
        await self.repo.add(message)
        await self.session.commit()
        logger.info("message_stored id=%s type=%s locale=%s", message.id, data.type, data.locale)
