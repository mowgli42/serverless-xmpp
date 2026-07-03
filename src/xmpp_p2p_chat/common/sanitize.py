"""Input sanitization helpers for message display and storage."""

from __future__ import annotations

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_message_body(text: str, max_length: int = 65536) -> str:
    """Strip control characters and cap length for safe local storage/display."""
    cleaned = _CONTROL_CHARS.sub("", text)
    if len(cleaned) > max_length:
        return cleaned[:max_length]
    return cleaned
