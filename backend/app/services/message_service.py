import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import content_hash, hash_ip
from app.models.contact_message import USER_AGENT_MAX, ContactMessage
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate

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

    async def submit(self, data: MessageCreate, client: ClientInfo) -> None:
        # Spam checks (link limit, rate limits, duplicates) are added in Phase 3.
        message = ContactMessage(
            name=data.name,
            email=data.email,
            type=data.type,
            content=data.content,
            locale=data.locale,
            ip_hash=hash_ip(client.ip, self.settings.ip_hash_secret.get_secret_value()),
            content_hash=content_hash(data.email, data.content),
            user_agent=client.user_agent[:USER_AGENT_MAX] if client.user_agent else None,
        )
        await self.repo.add(message)
        await self.session.commit()
        logger.info("message_stored id=%s type=%s locale=%s", message.id, data.type, data.locale)
