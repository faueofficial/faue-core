"""Idempotent consumption. Redelivery is normal, not exceptional."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from faue_core.events.envelope import Event


class IdempotentConsumer:
    """Marking and handling share a transaction. Otherwise a crash between them
    causes a redelivery to be skipped, which is worse than processing twice."""

    def __init__(
        self,
        handler: Callable[[Event, Any], Awaitable[None]],
        unit_of_work: Callable[[], Any],
        already_processed: Callable[[UUID, Any], Awaitable[bool]],
        mark_processed: Callable[[UUID, Any], Awaitable[None]],
    ) -> None:
        self._handler = handler
        self._uow = unit_of_work
        self._seen = already_processed
        self._mark = mark_processed

    async def handle(self, event: Event) -> None:
        async with self._uow() as session:
            if await self._seen(event.event_id, session):
                return
            await self._handler(event, session)
            await self._mark(event.event_id, session)
