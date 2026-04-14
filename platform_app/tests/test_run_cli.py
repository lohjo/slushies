import importlib
import sys

import pytest
from click.testing import CliRunner


def _reload_run_module(monkeypatch, env_name):
    monkeypatch.setenv("FLASK_ENV", env_name)
    if env_name == "production":
        monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/platform")
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    if "run" in sys.modules:
        del sys.modules["run"]
    import run  # noqa: F401
    return importlib.reload(sys.modules["run"])


def test_init_db_blocked_in_production(monkeypatch):
    run_module = _reload_run_module(monkeypatch, "production")
    runner = CliRunner()

    result = runner.invoke(run_module.app.cli, ["init-db"])

    assert result.exit_code != 0
    assert "disabled in production" in result.output


def test_init_db_allowed_in_development(monkeypatch):
    run_module = _reload_run_module(monkeypatch, "development")
    runner = CliRunner()

    result = runner.invoke(run_module.app.cli, ["init-db"])

    assert result.exit_code == 0
    assert "Database initialised." in result.output
