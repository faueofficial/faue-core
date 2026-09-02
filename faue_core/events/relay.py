"""Moves outbox rows to the broker.

Lives here rather than in a service because `api-gateway` and `ase` need the
identical loop, and a second implementation of "did this event get published"
drifts in ways nobody notices until an event is missing.

The relay is the only thing that ever sets `published_at`. Publishing and
stamping happen in one transaction: a crash between them republishes the event,
which consumers already tolerate because they are idempotent, whereas the
reverse ordering loses it outright.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import func, select

from faue_core.events.envelope import Event

#: Rows are claimed oldest-first, which gives per-producer ordering and nothing
#: stronger. A consumer that needs ordering between two event types has a design
#: problem the transport cannot solve for it.
DEFAULT_BATCH_SIZE = 100

#: After this many failures a row is parked: excluded from claiming, counted,
#: alerted on — never deleted. It represents a state change some consumer never
#: saw, and one poisonous row must not stop every event behind it.
DEFAULT_MAX_ATTEMPTS = 5


class TransportError(RuntimeError):
    """The broker refused or was unreachable. Retryable."""


class EventTransport(Protocol):
    async def send(self, event: Event) -> None: ...


class OutboxRelay:
    def __init__(
        self,
        outbox_model: Any,
        transport: EventTransport,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._outbox = outbox_model
        self._transport = transport
        self._batch_size = batch_size
        self._max_attempts = max_attempts

    async def drain(self, session: Any, *, commit: bool = True) -> int:
        """Publish one batch. Returns how many were sent.

        `commit=False` is for tests that need to hold the row locks open; the
        worker always commits, because an uncommitted stamp is a republish.
        """
        rows = (
            await session.execute(
                select(self._outbox)
                .where(
                    self._outbox.published_at.is_(None),
                    self._outbox.attempts < self._max_attempts,
                )
                .order_by(self._outbox.occurred_at)
                .limit(self._batch_size)
                # Two relay instances is the normal state on Railway, not an
                # edge case. Without SKIP LOCKED they either deadlock or both
                # publish the same row.
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()

        sent = 0
        for row in rows:
            try:
                await self._transport.send(_to_event(row))
            except TransportError:
                # The row stays unpublished. A broker outage delays events; it
                # must never lose them.
                row.attempts += 1
                continue

            row.published_at = datetime.now(UTC)
            sent += 1

        if commit:
            await session.commit()
        else:
            await session.flush()
        return sent

    async def parked(self, session: Any) -> int:
        """How many rows have exhausted their attempts.

        Anything above zero is an alert: those events exist and no consumer has
        seen them.
        """
        return (
            await session.execute(
                select(func.count())
                .select_from(self._outbox)
                .where(
                    self._outbox.published_at.is_(None),
                    self._outbox.attempts >= self._max_attempts,
                )
            )
        ).scalar_one()


def _to_event(row: Any) -> Event:
    """Rebuild the envelope a consumer will read.

    `occurred_at` comes from the row, never from the clock: the event happened
    when the state changed, not when the relay got round to it.
    """
    occurred_at = row.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)

    return Event(
        name=row.event_name,
        producer=getattr(row, "producer", None) or "api-gateway",
        payload=row.payload,
        trace_id=row.trace_id or "",
        user_id=row.user_id,
        version=row.event_version,
        event_id=row.id,
        occurred_at=occurred_at,
    )
