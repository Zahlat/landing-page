from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_info, get_db, get_settings_dep
from app.core.config import Settings
from app.schemas.message import MessageAccepted, MessageCreate
from app.services.message_service import ClientInfo, MessageService

router = APIRouter(tags=["messages"])


@router.post(
    "/messages",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageAccepted,
)
async def create_message(
    body: MessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    client: Annotated[ClientInfo, Depends(client_info)],
) -> MessageAccepted:
    await MessageService(db, settings).submit(body, client)
    return MessageAccepted()
