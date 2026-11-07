"""create contact_messages

Revision ID: 8f849e2624b4
Revises:
Create Date: 2026-11-07 21:28:05.637314

Enum columns are VARCHAR + CHECK (native_enum=False), not native PG ENUMs.
Their value lists are frozen here on purpose: changing an enum later means a new
migration that drops/recreates the ck_contact_messages_<col> constraint.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f849e2624b4"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _check_enum(name: str, *values: str, length: int) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=length)


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column(
            "type",
            _check_enum("type", "suggestion", "request", "question", "other", length=20),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("locale", _check_enum("locale", "ar", "en", length=2), nullable=False),
        sa.Column(
            "status",
            _check_enum("status", "new", "read", "archived", length=20),
            server_default="new",
            nullable=False,
        ),
        sa.Column("ip_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("content_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 100 AND name = btrim(name)",
            name=op.f("ck_contact_messages_name_length"),
        ),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254 AND email = lower(email)",
            name=op.f("ck_contact_messages_email_format"),
        ),
        sa.CheckConstraint(
            "char_length(content) BETWEEN 10 AND 5000",
            name=op.f("ck_contact_messages_content_length"),
        ),
        sa.CheckConstraint(
            "ip_hash IS NULL OR ip_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_contact_messages_ip_hash_hex"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_contact_messages_content_hash_hex"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_messages")),
    )

    desc = sa.literal_column
    # Admin list filtered by status (keyset pagination).
    op.create_index(
        "ix_contact_messages_status_created_id",
        "contact_messages",
        ["status", desc("created_at DESC"), desc("id DESC")],
    )
    # Admin list, no filter.
    op.create_index(
        "ix_contact_messages_created_id",
        "contact_messages",
        [desc("created_at DESC"), desc("id DESC")],
    )
    # Rate limit per IP / per email, duplicate check.
    op.create_index(
        "ix_contact_messages_ip_hash_created", "contact_messages", ["ip_hash", "created_at"]
    )
    op.create_index(
        "ix_contact_messages_email_created", "contact_messages", ["email", "created_at"]
    )
    op.create_index(
        "ix_contact_messages_content_hash_created",
        "contact_messages",
        ["content_hash", "created_at"],
    )


def downgrade() -> None:
    # Dropping the table drops its indexes and constraints too.
    op.drop_table("contact_messages")
