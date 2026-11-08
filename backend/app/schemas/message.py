from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.models.contact_message import CONTENT_MAX, CONTENT_MIN, EMAIL_MAX, NAME_MAX
from app.models.enums import Locale, MessageStatus, MessageType

LowerEmail = Annotated[EmailStr, Field(max_length=EMAIL_MAX), AfterValidator(str.lower)]


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=1, max_length=NAME_MAX)]
    email: LowerEmail
    type: MessageType
    content: Annotated[str, Field(min_length=CONTENT_MIN, max_length=CONTENT_MAX)]
    locale: Locale


class MessageAccepted(BaseModel):
    """The only thing the public endpoint ever returns."""

    status: Literal["received"] = "received"


class MessageListItem(BaseModel):
    """Admin list row: a preview only. Full text comes from the detail endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    name: str
    email: str
    type: MessageType
    status: MessageStatus
    preview: str


class MessageOut(BaseModel):
    """Admin detail. Explicit fields, so ip_hash and content_hash can't be serialized."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    type: MessageType
    content: str
    locale: Locale
    status: MessageStatus
    user_agent: str | None
    created_at: datetime
    read_at: datetime | None


class MessageStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: MessageStatus


class MessageStats(BaseModel):
    new: int
    read: int
    archived: int
