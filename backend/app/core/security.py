"""Hashing helpers. Raw IPs never leave this module un-hashed."""

import hashlib
import hmac
import ipaddress
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

UNKNOWN_IP = "unknown"

# --- passwords (Argon2id) ----------------------------------------------------------

# argon2-cffi defaults follow RFC 9106's low-memory profile and use Argon2id.
_hasher = PasswordHasher()

# Verified against when the email doesn't exist, so unknown and known emails take
# about the same time. Built at import with the same parameters as real hashes.
DUMMY_PASSWORD_HASH = _hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# --- session tokens ----------------------------------------------------------------


def new_session_token() -> str:
    """32 random bytes, URL-safe (43 chars). Only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_ip(raw: str | None) -> str:
    """Canonical text form of an IP, or "unknown" if missing/invalid."""
    if not raw:
        return UNKNOWN_IP
    try:
        return str(ipaddress.ip_address(raw.strip()))
    except ValueError:
        return UNKNOWN_IP


def hash_ip(ip: str, secret: str) -> str:
    """HMAC-SHA256(secret, ip) as 64 hex chars. Keyed so hashes can't be reversed by brute
    force over the IPv4 space without the secret."""
    return hmac.new(secret.encode(), ip.encode(), hashlib.sha256).hexdigest()


def normalize_content(content: str) -> str:
    return " ".join(content.split()).casefold()


def content_hash(email: str, content: str) -> str:
    """SHA-256 of normalized email + content, for duplicate detection."""
    payload = f"{email.strip().lower()}\n{normalize_content(content)}"
    return hashlib.sha256(payload.encode()).hexdigest()
