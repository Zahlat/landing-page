from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminLoginAttempt(Base):
    """One row per login attempt, for the per-IP login limit.

    Not in the original plan's schema; added (approved) because "max 10 login attempts
    per IP per 15 min" needs a durable, shared counter. Stores no email and no raw IP.
    """

    __tablename__ = "admin_login_attempts"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    ip_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    succeeded: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        sa.CheckConstraint("ip_hash ~ '^[0-9a-f]{64}$'", name="ip_hash_hex"),
        sa.Index("ix_admin_login_attempts_ip_hash_created", "ip_hash", "created_at"),
    )
