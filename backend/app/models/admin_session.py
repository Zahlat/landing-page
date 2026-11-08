from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminSession(Base):
    """Opaque server-side session. Only the SHA-256 of the token is stored; the raw
    token exists only in the admin's cookie."""

    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    token_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False, unique=True)
    admin_user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="token_hash_hex"),
        sa.CheckConstraint("expires_at > created_at", name="expires_after_created"),
    )
