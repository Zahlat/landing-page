"""Test data helpers."""

import hashlib
from datetime import timedelta
from itertools import count
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact_message import ContactMessage
from app.models.enums import Locale, MessageType

_seq = count(1)


def hex64(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


async def insert_message(
    db: AsyncSession,
    *,
    age: timedelta = timedelta(0),
    **overrides: Any,
) -> ContactMessage:
    """Insert a row directly (bypassing the API and spam rules), created `age` ago
    relative to the DB's now()."""
    n = next(_seq)
    values: dict[str, Any] = {
        "name": f"Person {n}",
        "email": f"person{n}@example.com",
        "type": MessageType.QUESTION,
        "content": f"Factory message number {n}",
        "locale": Locale.EN,
        "ip_hash": hex64(f"ip-{n}"),
        "content_hash": hex64(f"content-{n}"),
        "created_at": sa.func.now() - sa.literal(age, sa.Interval),
    }
    values.update(overrides)
    msg = ContactMessage(**values)
    db.add(msg)
    await db.flush()
    return msg
