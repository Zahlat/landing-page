from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_db, get_settings_dep
from app.core.config import Settings
from app.core.pagination import MAX_BIGINT
from app.models.contact_message import ContactMessage
from app.models.enums import MessageStatus, MessageType
from app.schemas.common import Page
from app.schemas.message import MessageListItem, MessageOut, MessageStats, MessageStatusUpdate
from app.services.message_service import MessageService

# The router-level dependency puts every route here behind an admin session.
router = APIRouter(
    prefix="/admin/messages", tags=["admin-messages"], dependencies=[Depends(current_admin)]
)

MessageId = Annotated[int, Path(ge=1, le=MAX_BIGINT)]


def get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> MessageService:
    return MessageService(db, settings)


Service = Annotated[MessageService, Depends(get_service)]


@router.get("", response_model=Page[MessageListItem])
async def list_messages(
    service: Service,
    message_status: Annotated[MessageStatus | None, Query(alias="status")] = None,
    message_type: Annotated[MessageType | None, Query(alias="type")] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Page[MessageListItem]:
    return await service.list_messages(
        status=message_status, message_type=message_type, cursor=cursor, limit=limit
    )


# Declared before /{message_id} so "stats" is never parsed as an id.
@router.get("/stats", response_model=MessageStats)
async def message_stats(service: Service) -> MessageStats:
    return await service.stats()


@router.get("/{message_id}", response_model=MessageOut)
async def get_message(message_id: MessageId, service: Service) -> ContactMessage:
    return await service.get_message(message_id)


@router.patch("/{message_id}", response_model=MessageOut)
async def update_message_status(
    message_id: MessageId, body: MessageStatusUpdate, service: Service
) -> ContactMessage:
    return await service.update_status(message_id, body.status)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: MessageId, service: Service) -> Response:
    await service.delete_message(message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
