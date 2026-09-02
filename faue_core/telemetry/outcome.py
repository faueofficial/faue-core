"""Did it work, and how completely?

Most operations here can half-succeed. A notification reaches the inbox but not
email; a relay pass publishes eight of ten rows; a generation fills four of five
slots. A boolean calls all of those `true`, and nobody investigates a `true`.

`Outcome` makes the middle state expressible, so a dashboard can alert on
"degraded but working" separately from "broken", and a log line says which
part did not happen and why.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from faue_core.telemetry.scrub import scrub

#: Reason codes are grouped by dashboards and alerted on, so they must be
#: stable identifiers rather than prose. A free-text sentence produces one
#: bucket per incident, which is the same as no grouping at all.
REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{2,48}$")


class OutcomeStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class Outcome:
    operation: str
    status: OutcomeStatus
    #: What actually happened — channel names, row ids, stage names.
    completed: tuple[str, ...] = ()
    #: What did not, and why. The reason is a code, not a sentence.
    skipped: dict[str, str] = field(default_factory=dict)
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Whether the caller's request was served at all.

        A partial outcome is `ok` **and** `degraded`: the user got something,
        and an operator still needs to know.
        """
        return self.status is not OutcomeStatus.FAILURE

    @property
    def degraded(self) -> bool:
        return self.status is not OutcomeStatus.SUCCESS

    @property
    def log_level(self) -> str:
        """Derived, not chosen. A caller cannot log a failure at INFO and have
        it disappear from the error rate."""
        return {
            OutcomeStatus.SUCCESS: "INFO",
            OutcomeStatus.PARTIAL: "WARNING",
            OutcomeStatus.FAILURE: "ERROR",
        }[self.status]

    # --- constructors ------------------------------------------------------

    @classmethod
    def success(
        cls, operation: str, *, completed: list[str], details: dict[str, Any] | None = None
    ) -> Outcome:
        return cls(
            operation=operation,
            status=OutcomeStatus.SUCCESS,
            completed=tuple(completed),
            details=details or {},
        )

    @classmethod
    def partial(
        cls,
        operation: str,
        *,
        completed: list[str],
        skipped: dict[str, str],
        details: dict[str, Any] | None = None,
    ) -> Outcome:
        if not completed:
            raise ValueError(
                f"{operation}: nothing completed — that is a failure, not a partial. "
                "A partial with no successes hides from every dashboard that "
                "alerts on failures."
            )
        if not skipped:
            raise ValueError(
                f"{operation}: a partial outcome must record what was skipped "
                "and why, or it is indistinguishable from a success."
            )
        for key, reason in skipped.items():
            _check_reason(f"{operation}.skipped[{key}]", reason)

        return cls(
            operation=operation,
            status=OutcomeStatus.PARTIAL,
            completed=tuple(completed),
            skipped=dict(skipped),
            details=details or {},
        )

    @classmethod
    def failure(
        cls,
        operation: str,
        *,
        reason: str,
        completed: list[str] | None = None,
        skipped: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> Outcome:
        """`skipped` is a parameter rather than something to bury in `details`.

        A failure often knows exactly which parts were attempted and why each
        one did not happen, and that per-part detail is the difference between
        "notify failed" and "both channels were duplicates of an event we
        already delivered". Passing it through `details` would also put it
        through the scrubber, where a channel named `email` collides with the
        PII key of the same name.
        """
        _check_reason(operation, reason)
        for key, why in (skipped or {}).items():
            _check_reason(f"{operation}.skipped[{key}]", why)

        return cls(
            operation=operation,
            status=OutcomeStatus.FAILURE,
            completed=tuple(completed or ()),
            skipped=dict(skipped or {}),
            reason=reason,
            details=details or {},
        )

    # --- logging -----------------------------------------------------------

    def as_log(self) -> dict[str, Any]:
        """The structured payload. Scrubbed, because outcomes are logged and
        anything reaching one obeys the same PII rules as any other log line."""
        payload: dict[str, Any] = {
            "operation": self.operation,
            "status": self.status.value,
            "completed_count": len(self.completed),
            "skipped_count": len(self.skipped),
        }
        if self.completed:
            payload["completed"] = list(self.completed)

        # `details` is caller-supplied and may hold anything, so it is scrubbed.
        payload.update(scrub(self.details))

        # `skipped` and `reason` are NOT scrubbed, and deliberately so. Every
        # value is validated against REASON_CODE, which no email address or
        # phone number can match — so there is nothing to redact. Scrubbing them
        # anyway loses real information: the scrubber is key-based, and `email`
        # is a channel name here as well as a PII field, so `{"email":
        # "no_verified_address"}` came back as `{"email": "[redacted]"}` and the
        # operator lost the only part that said what went wrong.
        if self.skipped:
            payload["skipped"] = dict(self.skipped)
        if self.reason:
            payload["reason"] = self.reason

        return payload


def _check_reason(operation: str, reason: str) -> None:
    if not reason:
        raise ValueError(f"{operation}: a failure must carry a reason code")
    if not REASON_CODE.match(reason):
        raise ValueError(
            f"{operation}: reason {reason!r} must be a stable snake_case code, "
            "not prose — dashboards group by this value."
        )
