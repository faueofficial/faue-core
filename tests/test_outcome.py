"""Outcomes.

Most of this system's operations can half-succeed, and "did it work?" as a
boolean throws that away. A notification that reached the inbox but not email,
a relay pass that published eight of ten rows, a generation that filled four of
five slots — all of those are `true` to a boolean and all of them need someone
to look.
"""

import pytest

from faue_core.telemetry.outcome import Outcome, OutcomeStatus


def test_a_clean_result_is_a_success():
    outcome = Outcome.success("notify.deliver", completed=["inbox", "email"])

    assert outcome.status is OutcomeStatus.SUCCESS
    assert outcome.ok is True
    assert outcome.degraded is False


def test_something_that_half_worked_is_partial():
    """The case a boolean loses. Nobody investigates a `true`."""
    outcome = Outcome.partial(
        "notify.deliver",
        completed=["inbox"],
        skipped={"email": "no_verified_address"},
    )

    assert outcome.status is OutcomeStatus.PARTIAL
    assert outcome.ok is True, "the caller's request was served, in part"
    assert outcome.degraded is True, "but something did not happen"


def test_a_failure_is_not_ok():
    outcome = Outcome.failure("notify.deliver", reason="template_missing")

    assert outcome.ok is False
    assert outcome.degraded is True


def test_a_partial_outcome_must_say_what_did_not_happen():
    """A partial with no skipped detail is indistinguishable from a success and
    tells an operator nothing."""
    with pytest.raises(ValueError, match="skipped"):
        Outcome.partial("notify.deliver", completed=["inbox"], skipped={})


def test_a_failure_must_carry_a_reason():
    """`failed: true` in a log line is the least useful thing a system can say."""
    with pytest.raises(ValueError, match="reason"):
        Outcome.failure("notify.deliver", reason="")


def test_nothing_completed_is_a_failure_not_a_partial():
    """A partial where nothing succeeded is a failure wearing a friendlier
    label, and it would hide in dashboards that only alert on failures."""
    with pytest.raises(ValueError, match="completed"):
        Outcome.partial("notify.deliver", completed=[], skipped={"email": "bounced"})


def test_the_log_payload_names_the_operation_and_the_counts():
    outcome = Outcome.partial(
        "relay.drain",
        completed=["a", "b"],
        skipped={"c": "transport_error"},
    )

    payload = outcome.as_log()

    assert payload["operation"] == "relay.drain"
    assert payload["status"] == "partial"
    assert payload["completed_count"] == 2
    assert payload["skipped_count"] == 1
    assert payload["skipped"] == {"c": "transport_error"}


def test_the_log_payload_is_scrubbed():
    """Outcomes are logged, so anything that reaches one has to survive the same
    PII rules as any other log line."""
    outcome = Outcome.failure(
        "notify.deliver", reason="bad_address", details={"email": "ada@example.com"}
    )

    assert "ada@example.com" not in str(outcome.as_log())


def test_a_reason_code_is_stable_enough_to_alert_on():
    """Dashboards group by this. A free-text sentence produces one bucket per
    incident, which is the same as no grouping at all."""
    with pytest.raises(ValueError, match="reason"):
        Outcome.failure("notify.deliver", reason="Could not send: the SMTP host said no")


def test_a_successful_outcome_may_still_record_context():
    outcome = Outcome.success("relay.drain", completed=["a"], details={"batch_size": 100})

    assert outcome.as_log()["batch_size"] == 100


def test_the_log_level_follows_the_status():
    """So a caller cannot log a failure at INFO and have it vanish."""
    assert Outcome.success("x", completed=["a"]).log_level == "INFO"
    degraded = Outcome.partial("x", completed=["a"], skipped={"b": "not_configured"})
    assert degraded.log_level == "WARNING"
    assert Outcome.failure("x", reason="boom").log_level == "ERROR"


def test_a_reason_survives_a_key_that_looks_like_pii():
    """`email` is a delivery channel here and a sensitive field name elsewhere.
    The key-based scrubber cannot tell them apart, and redacting the reason
    destroys the only part of the line that says what went wrong.

    Safe because every reason is validated against REASON_CODE, which no address
    or phone number can match.
    """
    outcome = Outcome.partial(
        "notify.deliver", completed=["inbox"], skipped={"email": "no_verified_address"}
    )

    assert outcome.as_log()["skipped"] == {"email": "no_verified_address"}


def test_caller_supplied_details_are_still_scrubbed():
    """The relaxation above applies only to validated reason codes."""
    outcome = Outcome.success(
        "x", completed=["a"], details={"email": "ada@example.com"}
    )

    assert outcome.as_log()["email"] == "[redacted]"


def test_a_failure_can_say_which_parts_failed_and_why():
    """The difference between "notify failed" and "both channels were
    duplicates of an event already delivered"."""
    outcome = Outcome.failure(
        "notify.deliver",
        reason="no_channel_delivered",
        skipped={"inbox": "duplicate", "email": "duplicate"},
    )

    assert outcome.as_log()["skipped"] == {"inbox": "duplicate", "email": "duplicate"}


def test_a_failures_skipped_reasons_are_validated_too():
    with pytest.raises(ValueError, match="reason"):
        Outcome.failure(
            "notify.deliver", reason="boom", skipped={"email": "it went wrong somehow"}
        )
