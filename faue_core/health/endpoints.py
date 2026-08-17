"""Health endpoints.

The distinction matters: a gateway whose ase connection is down must stay in
rotation and keep serving vault, saves and profile. Conflating the two takes the
whole product down for a partial outage.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Check = Callable[[], Awaitable[bool]]


def add_health_endpoints(app: Any, checks: dict[str, Check] | None = None) -> None:
    checks = checks or {}

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> dict[str, Any]:
        results = {name: await check() for name, check in checks.items()}
        ok = all(results.values())
        return {"status": "ok" if ok else "degraded", "checks": results}
