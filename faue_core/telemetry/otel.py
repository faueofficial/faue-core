"""OpenTelemetry wiring. One trace_id from the client through gateway, ase, the
model call, and back — propagated over HTTP headers and through event envelopes,
so asynchronous work stays attached to the user action that caused it."""

from __future__ import annotations

from typing import Any


def setup_telemetry(service_name: str, otlp_endpoint: str | None = None) -> None:
    raise NotImplementedError


def instrument_app(app: Any) -> None:
    raise NotImplementedError
