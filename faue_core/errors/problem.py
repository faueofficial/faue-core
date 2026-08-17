"""RFC 7807 problem documents."""

from __future__ import annotations

from typing import Any

from faue_core.errors.taxonomy import FaueError


def to_problem(error: FaueError, *, trace_id: str) -> dict[str, Any]:
    """`instance` carries the trace id — it is what turns a user's complaint into
    a resolvable ticket."""
    problem: dict[str, Any] = {
        "type": error.problem_type,
        "title": error.title,
        "status": error.status,
        "instance": trace_id,
    }
    if error.detail:
        problem["detail"] = error.detail
    if error.field:
        problem["errors"] = [{"field": error.field, "code": error.problem_type}]
    return problem
