import base64
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.errors import AppError
from app.core.pagination import MAX_BIGINT, Cursor, decode_cursor, encode_cursor

MOMENT = datetime(2026, 11, 8, 12, 30, 15, 123456, tzinfo=UTC)


def b64(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def test_round_trip_keeps_microseconds() -> None:
    assert decode_cursor(encode_cursor(MOMENT, 42)) == Cursor(MOMENT, 42)


def test_round_trip_normalizes_timezone() -> None:
    other_zone = MOMENT.astimezone(timezone(timedelta(hours=3)))
    assert decode_cursor(encode_cursor(other_zone, 7)) == Cursor(MOMENT, 7)


def test_cursor_is_url_safe() -> None:
    cursor = encode_cursor(MOMENT, 123456789)
    assert set(cursor) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not base64!",
        "%%%",
        "عربي",
        b64("no-separator"),
        b64("2026-11-08T12:00:00+00:00|"),
        b64("2026-11-08T12:00:00+00:00|abc"),
        b64("2026-11-08T12:00:00+00:00|-1"),
        b64("2026-11-08T12:00:00+00:00|0"),
        b64("2026-11-08T12:00:00+00:00|١٢"),
        b64(f"2026-11-08T12:00:00+00:00|{MAX_BIGINT + 1}"),
        b64("2026-11-08T12:00:00|5"),  # no timezone
        b64("not-a-date|5"),
        b64("0001-01-01T00:00:00+14:00|5"),  # overflows when converted to UTC
    ],
)
def test_malformed_cursor_is_422(bad: str) -> None:
    with pytest.raises(AppError) as exc:
        decode_cursor(bad)
    assert exc.value.status_code == 422
    assert exc.value.code == "invalid_cursor"


def test_largest_id_accepted() -> None:
    assert decode_cursor(b64(f"2026-11-08T12:00:00+00:00|{MAX_BIGINT}")).id == MAX_BIGINT
