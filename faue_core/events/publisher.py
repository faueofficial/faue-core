"""Event publishing.

Publishing REQUIRES a session. There is no API for publishing outside a
transaction, which is what makes "state saved but event lost" structurally
impossible rather than merely discouraged.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from faue_core.events.envelope import Event


class EventPublisher(Protocol):
    async def publish(self, event: Event, *, session: Any) -> None: ...


class OutboxPublisher:
    """Production. Writes the event row in the caller's transaction; a relay
    publishes it to the broker afterwards and stamps published_at."""

    def __init__(self, outbox_model: Any) -> None:
        self._outbox = outbox_model

    async def publish(self, event: Event, *, session: Any) -> None:
        session.add(
            self._outbox(
                id=event.event_id,
                event_name=event.name,
                event_version=event.version,
                user_id=event.user_id,
                trace_id=event.trace_id,
                payload=event.payload,
                occurred_at=event.occurred_at,
            )
        )


class InProcessPublisher:
    """Local development. Dispatches to registered handlers after commit, so
    handler logic is exercised without running a broker on a laptop."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Event], Awaitable[None]]]] = {}
        self._pending: list[Event] = []

    def subscribe(self, name: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        self._handlers.setdefault(name, []).append(handler)

    async def publish(self, event: Event, *, session: Any) -> None:
        self._pending.append(event)

    async def flush(self) -> None:
        pending, self._pending = self._pending, []
        for event in pending:
            for handler in self._handlers.get(event.name, []):
                await handler(event)
