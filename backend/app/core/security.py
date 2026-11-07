"""Hashing helpers. Raw IPs never leave this module un-hashed."""

import hashlib
import hmac
import ipaddress

UNKNOWN_IP = "unknown"


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
