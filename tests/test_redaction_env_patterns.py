from __future__ import annotations

import json

from allbrain.security import redaction
from allbrain.security.redaction import reload_secret_patterns, sanitize_text


def test_env_secret_patterns_are_merged(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALLBRAIN_SECRET_PATTERNS_JSON",
        json.dumps([{"pattern": r"hvs\.[A-Za-z0-9]{10,}", "name": "vault_token"}]),
    )
    reload_secret_patterns()
    try:
        cleaned = sanitize_text("token=hvs.ABCDEFGHIJKL and keep")
        assert "hvs.ABCDEFGHIJKL" not in cleaned
        assert "********" in cleaned
    finally:
        monkeypatch.delenv("ALLBRAIN_SECRET_PATTERNS_JSON", raising=False)
        reload_secret_patterns()


def test_invalid_env_secret_patterns_are_ignored(monkeypatch) -> None:
    monkeypatch.setenv("ALLBRAIN_SECRET_PATTERNS_JSON", "{not-json")
    reload_secret_patterns()
    try:
        assert len(redaction.SECRET_PATTERNS) == len(redaction._BUILTIN_SECRET_PATTERNS)
    finally:
        monkeypatch.delenv("ALLBRAIN_SECRET_PATTERNS_JSON", raising=False)
        reload_secret_patterns()


def test_redos_prone_env_patterns_are_skipped(monkeypatch) -> None:
    monkeypatch.setenv(
        "ALLBRAIN_SECRET_PATTERNS_JSON",
        json.dumps([{"pattern": r"(a+)+$", "name": "evil"}]),
    )
    reload_secret_patterns()
    try:
        assert len(redaction.SECRET_PATTERNS) == len(redaction._BUILTIN_SECRET_PATTERNS)
        assert not any(name == "evil" for _, name in redaction.SECRET_PATTERNS)
    finally:
        monkeypatch.delenv("ALLBRAIN_SECRET_PATTERNS_JSON", raising=False)
        reload_secret_patterns()


def test_list_events_accepts_long_agent_id() -> None:
    from allbrain.models.schemas import ListEventsInput

    long_id = "a" * 400
    data = ListEventsInput(agent_id=long_id)
    assert data.agent_id == long_id
