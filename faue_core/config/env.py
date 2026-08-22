"""Environment loading.

`pydantic-settings` reads `.env` for the `Settings` class only. Anything using
`os.environ` directly — Alembic's `env.py`, a preview script, a one-off worker —
sees nothing, and the failure is a confusing "missing DATABASE_URL" in a shell
where `.env` is sitting right there.

`load_env()` fixes that once, for everything.

**Existing environment variables always win.** That is what makes the same code
work locally (values from `.env`) and on Railway (values injected by the
platform, no file present) without a branch.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

_loaded = False


def load_env(*, start: Path | None = None, override: bool = False) -> list[Path]:
    """Load `.env` files, nearest last so the closest file wins.

    Walks from `start` up to the workspace root, loading every `.env` found.
    A shared workspace `.env` can hold values common to all services, and each
    service's own `.env` overrides it.

    Idempotent: repeated calls are cheap and do not re-read.
    """
    global _loaded
    if _loaded and not override:
        return []

    origin = (start or Path.cwd()).resolve()
    candidates: list[Path] = []

    for directory in (origin, *origin.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            candidates.append(candidate)
        # stop at the workspace root — never walk on into a home directory and
        # read a stranger's .env
        if (directory / "docs" / "repos.yaml").is_file():
            break

    ordered = list(reversed(candidates))          # furthest first

    # Merge rather than load sequentially. `load_dotenv(override=False)` would
    # also stop the NEARER file overriding the shared one, which is the wrong
    # precedence: a service .env must beat the workspace .env, while the real
    # environment beats both.
    merged: dict[str, str] = {}
    for path in ordered:
        merged.update({k: v for k, v in dotenv_values(path).items() if v is not None})

    for key, value in merged.items():
        if override or key not in os.environ:
            os.environ[key] = value

    _loaded = True
    return ordered


def require(name: str, *, hint: str | None = None) -> str:
    """Read a required variable, or fail with something actionable.

    A missing variable should say which one and where to put it, not raise a
    KeyError three frames into a request.
    """
    load_env()
    value = os.environ.get(name)
    if not value:
        message = f"{name} is not set."
        if hint:
            message += f" {hint}"
        message += "\nAdd it to .env (see .env.example), or export it."
        raise RuntimeError(message)
    return value
