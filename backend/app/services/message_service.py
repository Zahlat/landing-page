import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.pagination import decode_cursor, encode_cursor
from app.core.security import content_hash, hash_ip
from app.models.contact_message import USER_AGENT_MAX, ContactMessage
from app.models.enums import MessageStatus, MessageType
from app.repositories.message_repository import MessageRepository
from app.schemas.common import Page
from app.schemas.message import MessageCreate, MessageListItem, MessageStats
from app.services.spam_service import SpamService, SpamVerdict

logger = logging.getLogger("app.messages")


def _message_not_found() -> AppError:
    return AppError(404, "not_found", "Message not found.")


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

    # --- admin ----------------------------------------------------------------

    async def list_messages(
        self,
        *,
        status: MessageStatus | None,
        message_type: MessageType | None,
        cursor: str | None,
        limit: int,
    ) -> Page[MessageListItem]:
        rows = await self.repo.list_page(
            status=status,
            message_type=message_type,
            cursor=decode_cursor(cursor) if cursor is not None else None,
            limit=limit + 1,  # one extra row tells us whether another page exists
        )
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            next_cursor = encode_cursor(page[-1].created_at, page[-1].id)
        return Page[MessageListItem](
            items=[MessageListItem.model_validate(row) for row in page],
            next_cursor=next_cursor,
        )

    async def stats(self) -> MessageStats:
        counts = await self.repo.status_counts()
        return MessageStats(
            new=counts.get(MessageStatus.NEW, 0),
            read=counts.get(MessageStatus.READ, 0),
            archived=counts.get(MessageStatus.ARCHIVED, 0),
        )

    async def get_message(self, message_id: int) -> ContactMessage:
        message = await self.repo.get(message_id)
        if message is None:
            raise _message_not_found()
        return message

    async def update_status(self, message_id: int, status: MessageStatus) -> ContactMessage:
        message = await self.repo.get(message_id, for_update=True)
        if message is None:
            raise _message_not_found()
        # read_at records the first time a message left "new"; later moves keep it.
        if status is not MessageStatus.NEW and message.read_at is None:
            message.read_at = await self.repo.now()
        message.status = status
        await self.session.commit()
        logger.info("message_status_changed id=%s status=%s", message_id, status)
        return message

    async def delete_message(self, message_id: int) -> None:
        if not await self.repo.delete(message_id):
            raise _message_not_found()
        await self.session.commit()
        logger.info("message_deleted id=%s", message_id)
