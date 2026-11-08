"""Spam rules that run in FastAPI (plan table rows 4-7).

Order: link limit (no DB) -> per-IP limit -> per-email limit -> duplicate check.
Rate limits count stored rows in Postgres, so they are exact, survive restarts and
are shared between workers. Duplicates are not stored, so they don't count.
"""

import re
from datetime import timedelta
from enum import StrEnum

from app.core.config import Settings
from app.core.errors import AppError
from app.repositories.message_repository import MessageRepository, WindowCount
from app.services.limits import retry_after_seconds

RATE_WINDOW = timedelta(hours=1)

# Counts http(s):// URLs and bare www. hosts. Deliberately simple: the goal is to
# stop link-dump spam, not to parse every URL form.
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)


def count_links(content: str) -> int:
    return len(_URL_RE.findall(content))


__all__ = ["RATE_WINDOW", "SpamService", "SpamVerdict", "count_links", "retry_after_seconds"]


class SpamVerdict(StrEnum):
    ACCEPT = "accept"
    DUPLICATE = "duplicate"  # caller returns a fake 202 and stores nothing


class SpamService:
    def __init__(self, repo: MessageRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def check_links(self, content: str) -> None:
        if count_links(content) > self.settings.max_links_per_message:
            raise AppError(422, "too_many_links", "Too many links in the message.")

    async def check_rate_limits(self, ip_hash: str, email: str) -> None:
        await self.repo.lock(f"rl:ip:{ip_hash}", f"rl:email:{email}")

        by_ip = await self.repo.count_by_ip_since(ip_hash, RATE_WINDOW)
        if by_ip.count >= self.settings.rate_limit_ip_per_hour:
            self._raise_rate_limited(by_ip)

        by_email = await self.repo.count_by_email_since(email, RATE_WINDOW)
        if by_email.count >= self.settings.rate_limit_email_per_hour:
            self._raise_rate_limited(by_email)

    async def check_duplicate(self, content_hash: str) -> SpamVerdict:
        window = timedelta(hours=self.settings.duplicate_window_hours)
        if await self.repo.exists_content_hash_since(content_hash, window):
            return SpamVerdict.DUPLICATE
        return SpamVerdict.ACCEPT

    @staticmethod
    def _raise_rate_limited(window_count: WindowCount) -> None:
        retry = retry_after_seconds(window_count, RATE_WINDOW)
        # Same code/message for IP and email limits: don't tell clients which one hit.
        raise AppError(
            429,
            "rate_limited",
            "Too many messages. Please try again later.",
            headers={"Retry-After": str(retry)},
        )
