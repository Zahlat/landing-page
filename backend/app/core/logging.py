"""Structured key=value logging.

Rule: never log PII or secrets. No email, message content, IP (raw or hashed),
user agent, tokens or passwords. Log ids, codes, counts and durations instead.
"""

import logging

_FORMAT = "ts=%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if any(getattr(h, "_meraki", False) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler._meraki = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)
