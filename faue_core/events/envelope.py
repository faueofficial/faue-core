"""The event envelope. Payload shape varies; the envelope never does."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

EVENT_NAME = re.compile(r"^[a-z]+(\.[a-z_]+){1,3}$")


class InvalidEvent(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Event:
    """A fact: past tense, immutable, describing something that already happened.

    Payloads carry identifiers and minimal fields — never PII, never joined data.
    A consumer needing the full object fetches it.
    """

    name: str
    producer: str
    payload: dict[str, Any]
    trace_id: str
    user_id: UUID | None = None
    version: int = 1
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not EVENT_NAME.match(self.name):
            raise InvalidEvent(
                f"event name {self.name!r} must be noun.past_tense_verb, lower case"
            )
        if self.version < 1:
            raise InvalidEvent("version starts at 1")
        if self.occurred_at.tzinfo is None:
            raise InvalidEvent("occurred_at must be timezone-aware UTC")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "name": self.name,
            "version": self.version,
            "occurred_at": self.occurred_at.isoformat(),
            "producer": self.producer,
            "user_id": str(self.user_id) if self.user_id else None,
            "trace_id": self.trace_id,
            "payload": self.payload,
        }
