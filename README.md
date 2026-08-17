# faue-core

Shared runtime plumbing for FAUE services. Exists because four services need
identical plumbing and copy-paste drifts — the second copy of an event publisher
is where the outbox stops being reliable.

**Design:** [`docs/20-services/faue-core.md`](../docs/20-services/faue-core.md)

## What's here

| Package | Contents |
|---|---|
| `events/` | Envelope, outbox publisher, in-process publisher, idempotent consumer |
| `crypto/` | Envelope encryption, blind indexes |
| `consent/` | Purpose enum, defaults |
| `errors/` | Domain taxonomy, RFC 7807 translation |
| `telemetry/` | OpenTelemetry wiring, PII-scrubbing logs |
| `auth/` | Service JWT issue and verify |
| `config/` | Base settings |
| `health/` | `/healthz`, `/readyz`, `/metrics` |
| `requirements/` | **The shared dependency contract** |

## Implemented vs. skeleton

Working and tested: `events/envelope.py`, `events/publisher.py`,
`events/consumer.py`, `crypto/blind_index.py`, `consent/purposes.py`,
`errors/taxonomy.py`, `errors/problem.py`, `telemetry/scrub.py`,
`health/endpoints.py`.

Skeleton: `crypto/envelope.py`, `telemetry/otel.py`, `auth/service_jwt.py` —
these need a chosen crypto/OTel setup and are wired in during implementation.

```bash
pytest -q
```
