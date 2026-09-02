"""Event transports.

The in-process transport is the local default and the one most code runs
against, so its dispatch semantics matter as much as the broker's.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from faue_core.events.envelope import Event
from faue_core.events.transport import InProcessTransport

pytestmark = pytest.mark.asyncio


def _event(name: str = "quiz.completed") -> Event:
    return Event(name=name, producer="api-gateway", payload={"k": "v"}, trace_id="t")


async def test_a_subscribed_handler_receives_the_event(caplog):
    seen = []
    transport = InProcessTransport()
    transport.subscribe("quiz.completed", lambda e: seen.append(e) or _done())

    await transport.send(_event())

    assert [e.name for e in seen] == ["quiz.completed"]


async def test_an_event_with_no_handler_is_not_an_error():
    """Most events have no local consumer during development. Raising would
    make the relay retry something that will never succeed."""
    await InProcessTransport().send(_event("look.completed"))


async def test_every_handler_for_an_event_runs():
    first, second = [], []
    transport = InProcessTransport()
    transport.subscribe("quiz.completed", lambda e: first.append(e) or _done())
    transport.subscribe("quiz.completed", lambda e: second.append(e) or _done())

    await transport.send(_event())

    assert len(first) == 1 and len(second) == 1


async def test_one_failing_handler_does_not_stop_the_others():
    """A broker delivers to each queue independently, so the in-process
    transport must not couple handlers that production would isolate."""
    reached = []
    transport = InProcessTransport()

    async def explodes(event):
        raise RuntimeError("handler bug")

    transport.subscribe("quiz.completed", explodes)
    transport.subscribe("quiz.completed", lambda e: reached.append(e) or _done())

    await transport.send(_event())

    assert len(reached) == 1


async def test_a_failing_handler_does_not_fail_the_send():
    """Otherwise the relay marks the event unpublished and redelivers it to the
    handlers that already succeeded — turning one buggy handler into an
    infinite loop across all of them."""
    transport = InProcessTransport()

    async def explodes(event):
        raise RuntimeError("handler bug")

    transport.subscribe("quiz.completed", explodes)

    await transport.send(_event())     # must not raise


async def test_handlers_are_matched_by_exact_name():
    seen = []
    transport = InProcessTransport()
    transport.subscribe("quiz.completed", lambda e: seen.append(e) or _done())

    await transport.send(_event("quiz.completed.extra"))

    assert seen == []


def _done():
    """Lets the lambdas above return an awaitable without a def."""
    async def _noop():
        return None

    return _noop()
