"""Environment loading."""

import os
from pathlib import Path

import pytest

from faue_core.config import env as env_module
from faue_core.config.env import load_env, require


@pytest.fixture(autouse=True)
def _reset():
    env_module._loaded = False
    yield
    env_module._loaded = False


def test_loads_a_dotenv_file(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "repos.yaml").write_text("version: 1")
    (tmp_path / ".env").write_text("FAUE_TEST_VALUE=from-dotenv\n")
    monkeypatch.delenv("FAUE_TEST_VALUE", raising=False)

    load_env(start=tmp_path)
    assert os.environ["FAUE_TEST_VALUE"] == "from-dotenv"


def test_the_real_environment_wins(tmp_path, monkeypatch):
    """This is what makes the same code work locally and on Railway, where the
    platform injects variables and no file exists."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "repos.yaml").write_text("version: 1")
    (tmp_path / ".env").write_text("FAUE_TEST_VALUE=from-dotenv\n")
    monkeypatch.setenv("FAUE_TEST_VALUE", "from-real-environment")

    load_env(start=tmp_path)
    assert os.environ["FAUE_TEST_VALUE"] == "from-real-environment"


def test_a_nearer_dotenv_overrides_a_shared_one(tmp_path, monkeypatch):
    """A workspace .env holds what every service shares; a service .env wins."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "repos.yaml").write_text("version: 1")
    (tmp_path / ".env").write_text("FAUE_TEST_VALUE=workspace\n")

    service = tmp_path / "api-gateway"
    service.mkdir()
    (service / ".env").write_text("FAUE_TEST_VALUE=service\n")

    monkeypatch.delenv("FAUE_TEST_VALUE", raising=False)
    loaded = load_env(start=service)

    assert [p.parent.name for p in loaded] == [tmp_path.name, "api-gateway"]
    assert os.environ["FAUE_TEST_VALUE"] == "service"


def test_stops_at_the_workspace_root(tmp_path, monkeypatch):
    """Never walk past the workspace into a home directory and read a stranger's
    .env."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "repos.yaml").write_text("version: 1")
    (tmp_path / ".env").write_text("FAUE_TEST_VALUE=workspace\n")

    deep = tmp_path / "api-gateway" / "app" / "modules"
    deep.mkdir(parents=True)

    loaded = load_env(start=deep)
    assert all(tmp_path in p.parents or p.parent == tmp_path for p in loaded)


def test_is_idempotent(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "repos.yaml").write_text("version: 1")
    (tmp_path / ".env").write_text("FAUE_TEST_VALUE=x\n")

    first = load_env(start=tmp_path)
    second = load_env(start=tmp_path)
    assert first and second == []


def test_missing_file_is_not_an_error(tmp_path):
    """Railway has no .env; that must not be a failure."""
    assert load_env(start=tmp_path) == []


def test_require_names_the_variable_and_the_fix(monkeypatch):
    monkeypatch.delenv("FAUE_ABSENT", raising=False)
    with pytest.raises(RuntimeError) as exc:
        require("FAUE_ABSENT", hint="Get it from the Resend dashboard.")

    message = str(exc.value)
    assert "FAUE_ABSENT" in message
    assert "Resend dashboard" in message
    assert ".env" in message
