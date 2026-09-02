"""Structured JSON logging.

One line per event, always carrying `trace_id`, `service` and `environment`, so
a log line can be joined to the request that produced it without every call site
remembering to pass context.

Scrubbing is applied by the formatter rather than by callers. A rule that
depends on every developer remembering it is not a rule — and the mistake that
actually happens is interpolating a variable called `email` into a message.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from typing import Any

from faue_core.telemetry.outcome import Outcome
from faue_core.telemetry.scrub import scrub, scrub_text

#: Request-scoped context. A ContextVar rather than a thread-local because the
#: server is async: one thread serves many requests concurrently and a
#: thread-local would attribute log lines to the wrong one.
_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})

#: Attributes the stdlib puts on every record. Anything outside this set was put
#: there by a caller via `extra=` and belongs in the payload.
_RESERVED = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}

#: Record attribute naming fields that must not be scrubbed again. Set by
#: `log_outcome`; nothing else should use it without the same guarantee that the
#: values are validated codes rather than free text.
PRESCRUBBED_ATTR = "_faue_prescrubbed"

_configured = False


def bind(**values: Any) -> None:
    """Attach context to every subsequent log line in this task."""
    _CONTEXT.set({**_CONTEXT.get(), **values})


def clear() -> None:
    """Drop the context. Called at the end of a request so nothing leaks into
    the next one served by the same worker."""
    _CONTEXT.set({})


def context() -> dict[str, Any]:
    return dict(_CONTEXT.get())


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str, environment: str) -> None:
        super().__init__()
        self._service = service
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service,
            "environment": self._environment,
            # Scrubbed even though it is a developer-written string: an f-string
            # is exactly how an address ends up in a message body, and the
            # key-based rules cannot see inside one.
            "message": scrub_text(record.getMessage()),
        }
        payload.update(_CONTEXT.get())

        # A caller may declare that some fields are already safe. `Outcome`
        # does: its reason codes are regex-validated identifiers that no address
        # or phone number can match, and scrubbing them by key destroys the
        # only part of the line saying what went wrong — `email` is a delivery
        # channel here as well as a PII field name.
        prescrubbed = set(getattr(record, PRESCRUBBED_ATTR, ()) or ())

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED and key != PRESCRUBBED_ATTR
        }
        payload.update(
            {
                key: value if key in prescrubbed else scrub(value, key=key)
                for key, value in extras.items()
            }
        )

        if record.exc_info:
            exc_type, exc_value, tb = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else "Unknown",
                # The message may carry interpolated user data.
                "message": scrub_text(str(exc_value)),
                "traceback": "".join(traceback.format_exception(*record.exc_info)),
            }

        return json.dumps(payload, default=str)


def configure(
    *, service: str, environment: str, level: str = "INFO", stream: Any = None
) -> None:
    """Install the JSON handler on the root logger.

    Idempotent: the app factory and every worker call it, and doing so twice
    must not double every line.
    """
    global _configured

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=stream or sys.stderr)
    handler.setFormatter(JsonFormatter(service=service, environment=environment))
    root.addHandler(handler)
    root.setLevel(level)

    _configured = True


def log_outcome(logger: logging.Logger, outcome: Outcome, message: str | None = None) -> None:
    """Emit an outcome at the level its status implies.

    The level is derived rather than passed, so a failure cannot be logged at
    INFO and quietly leave the error rate.
    """
    payload = outcome.as_log()
    logger.log(
        getattr(logging, outcome.log_level),
        message or f"{outcome.operation} {outcome.status.value}",
        extra={**payload, PRESCRUBBED_ATTR: ("skipped", "reason")},
    )
