from datetime import UTC, datetime
from uuid import uuid4

import pytest

from faue_core.events.envelope import Event, InvalidEvent


def make(**overrides):
    base = dict(name="look.completed", producer="ase", payload={"job_id": str(uuid4())},
                trace_id="4bf92f3577b34da6a3ce929d0e0e4736")
    return Event(**{**base, **overrides})


def test_valid_event_round_trips():
    event = make()
    body = event.to_dict()
    assert body["name"] == "look.completed"
    assert body["version"] == 1
    assert body["user_id"] is None


@pytest.mark.parametrize("bad", ["LookCompleted", "look", "look.Completed", "look completed", ""])
def test_event_names_must_be_past_tense_dotted(bad):
    with pytest.raises(InvalidEvent):
        make(name=bad)


def test_naive_timestamps_rejected():
    with pytest.raises(InvalidEvent):
        make(occurred_at=datetime(2026, 8, 17, 12, 0))


def test_events_are_immutable():
    event = make()
    with pytest.raises(Exception):
        event.name = "look.failed"  # type: ignore[misc]


def test_occurred_at_is_utc_aware():
    assert make().occurred_at.tzinfo is not None
    assert make(occurred_at=datetime.now(UTC)).occurred_at.tzinfo is UTC
