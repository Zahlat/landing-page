from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.models.contact_message import CONTENT_MAX, CONTENT_MIN, EMAIL_MAX, NAME_MAX
from app.models.enums import Locale, MessageType

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
