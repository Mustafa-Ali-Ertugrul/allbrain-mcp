"""Tests for rate-limit environment-variable initialisation hardening."""

from __future__ import annotations

import importlib

import pytest

import allbrain.security.rate_limit as rl


@pytest.fixture(autouse=True)
def cleanup_rate_limit_env(monkeypatch):
    yield
    monkeypatch.delenv("ALLBRAIN_RATE_LIMIT_RPM", raising=False)
    monkeypatch.delenv("ALLBRAIN_RATE_LIMIT_RPS", raising=False)
    importlib.reload(rl)


def _reload_with_env(monkeypatch, rpm: str | None, rps: str | None):
    if rpm is None:
        monkeypatch.delenv("ALLBRAIN_RATE_LIMIT_RPM", raising=False)
    else:
        monkeypatch.setenv("ALLBRAIN_RATE_LIMIT_RPM", rpm)
    if rps is None:
        monkeypatch.delenv("ALLBRAIN_RATE_LIMIT_RPS", raising=False)
    else:
        monkeypatch.setenv("ALLBRAIN_RATE_LIMIT_RPS", rps)
    return importlib.reload(rl)


def test_defaults_when_unset(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, None, None)
    assert mod._DEFAULT_RPM == 100_000
    assert mod._DEFAULT_RPS == 1_000


def test_valid_override(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, "500", "50")
    assert mod._DEFAULT_RPM == 500
    assert mod._DEFAULT_RPS == 50


def test_invalid_rpm_falls_back(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, "not-a-number", None)
    assert mod._DEFAULT_RPM == 100_000


def test_invalid_rps_falls_back(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, None, "garbage")
    assert mod._DEFAULT_RPS == 1_000


def test_negative_value_falls_back(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, "-5", "0")
    assert mod._DEFAULT_RPM == 100_000
    assert mod._DEFAULT_RPS == 1_000


def test_check_tool_rate_still_works_after_reload(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, "100", "20")
    mod.reset_rate_limits()
    # Should not raise with generous limits
    mod.check_tool_rate("reload_test")
    mod.check_tool_rate("reload_test")
