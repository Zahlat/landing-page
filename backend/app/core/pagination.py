"""Opaque keyset cursors: URL-safe base64 of "<created_at ISO>|<id>" for the last row."""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.errors import AppError

MAX_BIGINT = 2**63 - 1


@dataclass(frozen=True)
class Cursor:
    created_at: datetime
    id: int


def encode_cursor(created_at: datetime, row_id: int) -> str:
    raw = f"{created_at.astimezone(UTC).isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def decode_cursor(value: str) -> Cursor:
    """Parse a client-supplied cursor; anything malformed is a 422, never a 500."""
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True).decode()
        created_text, separator, id_text = raw.partition("|")
        if not separator or not (id_text.isascii() and id_text.isdigit()):
            raise ValueError("bad cursor layout")
        row_id = int(id_text)
        created_at = datetime.fromisoformat(created_text)
        if created_at.tzinfo is None or not 1 <= row_id <= MAX_BIGINT:
            raise ValueError("bad cursor values")
        # Normalizing also rejects datetimes that overflow once converted to UTC.
        return Cursor(created_at=created_at.astimezone(UTC), id=row_id)
    except (ValueError, OverflowError) as exc:
        raise AppError(422, "invalid_cursor", "Invalid cursor.") from exc
