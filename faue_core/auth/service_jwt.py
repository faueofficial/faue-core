"""Service-to-service tokens.

Five-minute life, audience-scoped. The audience check is what stops a user token
from ever working on an internal endpoint, even if one ended up in the wrong header.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceClaims:
    issuer: str
    audience: str
    expires_at: int


def issue_service_token(audience: str, secret: str, ttl: int = 300) -> str:
    raise NotImplementedError


def verify_service_token(token: str, secret: str, expected_audience: str) -> ServiceClaims:
    raise NotImplementedError
