import pytest

from app.core.security import UNKNOWN_IP, content_hash, hash_ip, normalize_ip


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        (" 203.0.113.7 ", "203.0.113.7"),
        ("2001:DB8::1", "2001:db8::1"),
        ("2001:db8:0:0:0:0:0:1", "2001:db8::1"),
        (None, UNKNOWN_IP),
        ("", UNKNOWN_IP),
        ("not-an-ip", UNKNOWN_IP),
        ("1.2.3.4, 5.6.7.8", UNKNOWN_IP),
        ("999.1.1.1", UNKNOWN_IP),
    ],
)
def test_normalize_ip(raw: str | None, expected: str) -> None:
    assert normalize_ip(raw) == expected


def test_hash_ip_is_keyed_hex() -> None:
    h = hash_ip("203.0.113.7", "secret-one")
    assert len(h) == 64
    assert int(h, 16) >= 0
    assert h == hash_ip("203.0.113.7", "secret-one")
    assert h != hash_ip("203.0.113.7", "secret-two")
    assert h != hash_ip("203.0.113.8", "secret-one")


def test_content_hash_normalizes_case_and_whitespace() -> None:
    a = content_hash("Sara@Example.com", "Hello   there\n\nfriend")
    b = content_hash(" sara@example.com ", "hello there friend")
    assert a == b
    assert len(a) == 64


def test_content_hash_depends_on_email_and_content() -> None:
    base = content_hash("a@example.com", "same content here")
    assert base != content_hash("b@example.com", "same content here")
    assert base != content_hash("a@example.com", "different content")
