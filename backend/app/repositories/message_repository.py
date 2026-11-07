from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact_message import ContactMessage


class MessageRepository:
    """SQL only; no business rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, message: ContactMessage) -> ContactMessage:
        self.session.add(message)
        await self.session.flush()
        return message
