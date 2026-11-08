import math
from datetime import datetime, timedelta

from app.repositories.common import WindowCount


def seconds_until(moment: datetime, now: datetime) -> int:
    """Whole seconds from now until moment, never below 1 (for Retry-After)."""
    return max(1, math.ceil((moment - now).total_seconds()))


def retry_after_seconds(window_count: WindowCount, window: timedelta) -> int:
    """Seconds until the oldest counted row leaves the window (always >= 1)."""
    if window_count.oldest is None:
        return 1
    return seconds_until(window_count.oldest + window, window_count.now)
