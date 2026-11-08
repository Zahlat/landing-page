from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.message import LowerEmail

# Passwords are never trimmed (overrides the model-wide str_strip_whitespace).
# Capped so a huge password can't be used to burn CPU in Argon2.
Password = Annotated[str, StringConstraints(strip_whitespace=False, min_length=1, max_length=1024)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: LowerEmail
    password: Password


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime


class AdminMe(BaseModel):
    email: str
