"""Where a published event actually goes.

Two implementations behind one interface, selected by `EVENT_TRANSPORT`:

- `InProcessTransport` — the documented local default. Dispatches straight to
  registered handlers so a laptop exercises handler logic with no broker
  running.
- `RabbitTransport` — staging and production. Topic exchange, routing key is
  the event name.

The relay does not know which it has, which is the point: the same code path is
exercised locally and in production, and there is no `if ENVIRONMENT ==` between
them.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from faue_core.events.envelope import Event
from faue_core.events.relay import TransportError

logger = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]

EXCHANGE = "faue.events"


class InProcessTransport:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    async def send(self, event: Event) -> None:
        """Dispatch to every handler for this event name.

        A handler that raises is logged and skipped rather than propagated. A
        broker delivers to each queue independently, so coupling handlers here
        would let one bug redeliver an event to handlers that already succeeded
        — the same buggy handler then fails again, forever.

        An event with no handler is not an error. Most events have no local
        consumer during development, and raising would make the relay retry
        something that can never succeed.
        """
        for handler in self._handlers.get(event.name, []):
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "in-process handler failed",
                    extra={"event_name": event.name, "event_id": str(event.event_id)},
                )


class RabbitTransport:
    """Topic exchange, durable, publisher-confirmed.

    Confirms are not optional: without them `basic_publish` returns as soon as
    the bytes leave the process, the relay stamps `published_at`, and a broker
    that drops the message loses the event with the outbox showing it as sent.
    """

    def __init__(self, connection: Any, *, exchange: str = EXCHANGE) -> None:
        self._connection = connection
        self._exchange_name = exchange
        self._exchange: Any = None

    async def _ensure_exchange(self) -> Any:
        if self._exchange is None:
            import aio_pika

            channel = await self._connection.channel(publisher_confirms=True)
            self._exchange = await channel.declare_exchange(
                self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
            )
        return self._exchange

    async def send(self, event: Event) -> None:
        import json

        import aio_pika

        try:
            exchange = await self._ensure_exchange()
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(event.to_dict()).encode(),
                    content_type="application/json",
                    message_id=str(event.event_id),
                    # Survives a broker restart. An event that only exists in
                    # RAM defeats the outbox that carefully persisted it.
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    headers={"trace_id": event.trace_id},
                ),
                routing_key=event.name,
            )
        except Exception as exc:
            # The relay distinguishes retryable transport failure from a bug.
            # Anything reaching here is the former: the row stays unpublished
            # and its attempt count goes up.
            self._exchange = None       # force a fresh channel next time
            raise TransportError(f"publish failed: {exc}") from exc
