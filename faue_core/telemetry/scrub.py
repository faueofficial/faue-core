"""PII scrubbing for structured logs.

Blunt by design: it catches the mistake that actually happens, which is
interpolating a variable called `email` into a log line.
"""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = frozenset({
    "email", "phone", "name", "display_name", "username", "full_name",
    "password", "token", "access_token", "refresh_token", "secret", "api_key",
    "authorization", "measurements", "height_cm", "body_shape",
    "latitude", "longitude", "address", "prompt", "content", "text",
})

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\s-]{8,})(?!\d)")

REDACTED = "[redacted]"


def scrub(value: Any, *, key: str | None = None) -> Any:
    if key and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, dict):
        return {k: scrub(v, key=k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(scrub(v) for v in value)
    if isinstance(value, str):
        value = EMAIL_RE.sub(REDACTED, value)
        value = PHONE_RE.sub(REDACTED, value)
    return value


def scrub_text(text: str) -> str:
    """Scrub a bare string — a log message, an exception message.

    The key-based rules cannot see inside an f-string, and an f-string is
    exactly how an address reaches a message body.
    """
    return scrub(text)
