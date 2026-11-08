from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

EMAIL_MAX = 254


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(EMAIL_MAX), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )
    failed_login_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default=sa.text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        sa.CheckConstraint(
            f"char_length(email) BETWEEN 3 AND {EMAIL_MAX} AND email = lower(email)",
            name="email_format",
        ),
        sa.CheckConstraint("password_hash LIKE '$argon2id$%'", name="password_hash_argon2id"),
        sa.CheckConstraint("failed_login_count >= 0", name="failed_login_count_nonneg"),
    )
