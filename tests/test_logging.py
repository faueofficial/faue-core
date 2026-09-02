"""Structured logging.

JSON, always carrying trace_id, service and environment. The rules that matter
are the ones that fail quietly: a PII field reaching a log line, or a level that
does not match what happened.
"""

import json
import logging

import pytest

from faue_core.telemetry import logs
from faue_core.telemetry.outcome import Outcome


@pytest.fixture
def emitted():
    """Logs into an explicit buffer.

    Not capsys: how pytest captures a stream is an implementation detail of the
    test runner, and this needs to assert on what the formatter produces.
    """
    import io

    buffer = io.StringIO()
    # Context is task-scoped and pytest runs these in one task, so a binding
    # from an earlier test would otherwise appear in a later one's output.
    logs.clear()
    logs.configure(
        service="api-gateway", environment="test", level="DEBUG", stream=buffer
    )

    def _read():
        return [
            json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()
        ]

    yield _read
    logs.clear()


def test_a_log_line_is_json(emitted):
    logging.getLogger("t").info("something happened")

    line = emitted()[0]
    assert line["message"] == "something happened"
    assert line["level"] == "INFO"


def test_every_line_carries_service_and_environment(emitted):
    logging.getLogger("t").info("x")

    line = emitted()[0]
    assert line["service"] == "api-gateway"
    assert line["environment"] == "test"


def test_the_trace_id_is_attached_from_context(emitted):
    """So a log line can be joined to the request that produced it without the
    caller remembering to pass it."""
    logs.bind(trace_id="abc123")
    logging.getLogger("t").info("x")

    assert emitted()[0]["trace_id"] == "abc123"


def test_bound_context_does_not_leak_between_requests(emitted):
    logs.bind(trace_id="first")
    logs.clear()
    logging.getLogger("t").info("x")

    assert emitted()[0].get("trace_id") in (None, "")


def test_extra_fields_are_scrubbed(emitted):
    """The mistake that actually happens: interpolating a variable called
    `email` into a log line."""
    logging.getLogger("t").info("signed in", extra={"email": "ada@example.com"})

    assert "ada@example.com" not in json.dumps(emitted()[0])


def test_an_email_in_the_message_body_is_scrubbed(emitted):
    """Belt and braces — the key-based rule cannot catch an f-string."""
    logging.getLogger("t").info("sent to ada@example.com")

    assert "ada@example.com" not in json.dumps(emitted()[0])


def test_an_outcome_is_logged_at_the_level_its_status_implies(emitted):
    logs.log_outcome(
        logging.getLogger("t"),
        Outcome.partial("notify.deliver", completed=["inbox"],
                        skipped={"email": "no_verified_address"}),
    )

    line = emitted()[0]
    assert line["level"] == "WARNING"
    assert line["status"] == "partial"
    assert line["operation"] == "notify.deliver"
    assert line["skipped"] == {"email": "no_verified_address"}


def test_a_successful_outcome_is_info(emitted):
    logs.log_outcome(
        logging.getLogger("t"), Outcome.success("relay.drain", completed=["a"])
    )

    assert emitted()[0]["level"] == "INFO"


def test_a_failed_outcome_is_error_and_names_the_reason(emitted):
    logs.log_outcome(
        logging.getLogger("t"), Outcome.failure("relay.drain", reason="broker_unreachable")
    )

    line = emitted()[0]
    assert line["level"] == "ERROR"
    assert line["reason"] == "broker_unreachable"


def test_an_exception_is_rendered_with_its_type(emitted):
    """A stack trace in a JSON field, not spread across twenty unparseable
    lines that no aggregator can group."""
    logger = logging.getLogger("t")
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("handler failed")

    line = emitted()[0]
    assert line["exception"]["type"] == "ValueError"
    assert "boom" in line["exception"]["message"]
    assert "Traceback" in line["exception"]["traceback"]


def test_configure_is_idempotent():
    """Called by the app factory and by each worker. Twice must not double
    every line."""
    import io

    buffer = io.StringIO()
    logs.configure(service="api-gateway", environment="test", stream=buffer)
    logs.configure(service="api-gateway", environment="test", stream=buffer)

    logging.getLogger("t").info("once")

    assert len(buffer.getvalue().strip().splitlines()) == 1
