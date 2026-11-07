from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import Locale, MessageStatus, MessageType, str_enum_column_type

NAME_MAX = 100
EMAIL_MAX = 254
CONTENT_MIN = 10
CONTENT_MAX = 5000
USER_AGENT_MAX = 512


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(NAME_MAX), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(EMAIL_MAX), nullable=False)
    type: Mapped[MessageType] = mapped_column(
        str_enum_column_type(MessageType, name="type", length=20), nullable=False
    )
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    locale: Mapped[Locale] = mapped_column(
        str_enum_column_type(Locale, name="locale", length=2), nullable=False
    )
    status: Mapped[MessageStatus] = mapped_column(
        str_enum_column_type(MessageStatus, name="status", length=20),
        nullable=False,
        default=MessageStatus.NEW,
        server_default=MessageStatus.NEW.value,
    )
    # Nullable so purge-old-data can blank it after 90 days.
    ip_hash: Mapped[str | None] = mapped_column(sa.CHAR(64))
    content_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(sa.String(USER_AGENT_MAX))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {NAME_MAX} AND name = btrim(name)",
            name="name_length",
        ),
        sa.CheckConstraint(
            f"char_length(email) BETWEEN 3 AND {EMAIL_MAX} AND email = lower(email)",
            name="email_format",
        ),
        sa.CheckConstraint(
            f"char_length(content) BETWEEN {CONTENT_MIN} AND {CONTENT_MAX}",
            name="content_length",
        ),
        sa.CheckConstraint("ip_hash IS NULL OR ip_hash ~ '^[0-9a-f]{64}$'", name="ip_hash_hex"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_hex"),
        sa.Index(
            "ix_contact_messages_status_created_id",
            "status",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ),
        sa.Index("ix_contact_messages_created_id", sa.text("created_at DESC"), sa.text("id DESC")),
        sa.Index("ix_contact_messages_ip_hash_created", "ip_hash", "created_at"),
        sa.Index("ix_contact_messages_email_created", "email", "created_at"),
        sa.Index("ix_contact_messages_content_hash_created", "content_hash", "created_at"),
    )
