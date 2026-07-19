"""Regression tests for v0.2.4 fixes.

Covers:
- Step 1: StateEngine.apply_events() single-pass equivalence
- Step 3: _SAFE_KEY_DENYLIST value-based fallback
- Step 4: iter_events_through_cursor generator
- Step 5: open_write_session uses threading.Event().wait()
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

from allbrain.core import StateEngine
from allbrain.models.schemas import EventRead
from allbrain.security.redaction import (
    _is_sensitive_key,
    _matches_any_secret_pattern,
    sanitize_payload,
)
from tests._helpers import make_context_from_repo, make_openai_key, make_repo

# ---------------------------------------------------------------------------
# Step 1: StateEngine.apply_events() single-pass equivalence
# ---------------------------------------------------------------------------


def _make_event(event_id: str, type: str, payload: dict, file_path: str | None = None) -> EventRead:
    return EventRead(
        id=event_id,
        project_id=1,
        session_id=1,
        type=type,
        source="test",
        file_path=file_path,
        payload=payload,
        task_hint=None,
        importance=None,
        created_at=datetime.now(UTC),
    )


def _apply_events_double_pass(base_state, events, git=None):
    """Old implementation with two StateMachine passes (reference)."""
    from allbrain.core.merge import StateMerger
    from allbrain.core.state_machine import ProjectState, StateMachine

    if not events:
        state = dict(base_state)
        state["git"] = git or {}
        return state

    final_machine = StateMachine(ProjectState.from_dict(base_state))
    for event in events:
        final_machine.apply(event)
    final_state = final_machine.get_state().to_dict()

    delta_machine = StateMachine()
    for event in events:
        delta_machine.apply(event)
    delta_state = delta_machine.get_state().to_dict()
    delta_state["goal"] = final_state["goal"]
    delta_state["working_files"] = final_state["working_files"]
    delta_state["open_tasks"] = final_state["open_tasks"]
    delta_state["open_task_refs"] = final_state.get("open_task_refs", {})
    delta_state["last_event_id"] = final_state["last_event_id"]
    delta_state["last_working_file"] = final_state["last_working_file"]
    delta_state["event_count"] = len(events)
    delta_state["git"] = git or {}
    return StateMerger().merge(base_state, delta_state)


def test_apply_events_single_pass_equivalence() -> None:
    """Single-pass implementation must produce identical results to the old two-pass."""
    base_state = {
        "goal": "Original goal",
        "working_files": ["old.py"],
        "open_tasks": ["Old task"],
        "completed_tasks": [],
        "blocked": [],
        "failures": [],
        "tool_usage": [],
        "last_event_id": "0",
        "last_working_file": "old.py",
        "event_count": 5,
        "git": {},
    }

    events = []
    for i in range(500):
        if i % 4 == 0:
            events.append(_make_event(f"evt-{i}", "task_started", {"task": f"Task {i % 7}"}))
        elif i % 4 == 1:
            events.append(_make_event(f"evt-{i}", "task_completed", {"task": f"Task {i % 7}"}))
        elif i % 4 == 2:
            events.append(_make_event(f"evt-{i}", "file_modified", {}, file_path=f"module_{i % 13}.py"))
        else:
            events.append(_make_event(f"evt-{i}", "failure", {"error": f"fail-{i}"}))

    old_result = _apply_events_double_pass(base_state, events, git={"branch": "main"})
    new_result = StateEngine().apply_events(base_state, events, git={"branch": "main"})

    for key in ["goal", "working_files", "open_tasks", "completed_tasks",
                 "blocked", "failures", "tool_usage", "last_event_id",
                 "last_working_file", "event_count", "git"]:
        assert old_result[key] == new_result[key], f"Mismatch on key '{key}'"


# ---------------------------------------------------------------------------
# Step 3: _SAFE_KEY_DENYLIST value-based fallback
# ---------------------------------------------------------------------------


def test_generic_key_with_secret_value_is_redacted() -> None:
    """{"key": "sk-ant-api03-..."} must be redacted via value-based fallback."""
    secret = "sk-ant-api03-" + "a" * 36
    result = sanitize_payload({"key": secret})
    assert result["key"] == "********"


def test_generic_key_with_safe_value_untouched() -> None:
    """{"key": "user-theme"} must NOT be redacted — safe value."""
    result = sanitize_payload({"key": "user-theme"})
    assert result["key"] == "user-theme"


def test_keys_with_secret_value_is_redacted() -> None:
    """{"keys": "sk-ant-..."} must be redacted."""
    secret = "sk-ant-" + "a" * 36
    result = sanitize_payload({"keys": secret})
    assert result["keys"] == "********"


def test_keys_with_safe_value_untouched() -> None:
    """{"keys": ["a", "b"]} must NOT be redacted — list value, not a secret pattern."""
    result = sanitize_payload({"keys": ["a", "b"]})
    assert result["keys"] == ["a", "b"]


def test_is_sensitive_key_value_fallback() -> None:
    """_is_sensitive_key returns True for "key" only when value matches a secret pattern."""
    assert _is_sensitive_key("key", value="sk-ant-" + "a" * 36) is True
    assert _is_sensitive_key("key", value="user-theme") is False
    assert _is_sensitive_key("key") is False  # no value → safe


def test_matches_any_secret_pattern() -> None:
    """_matches_any_secret_pattern detects known secret formats."""
    assert _matches_any_secret_pattern("sk-ant-" + "a" * 36) is True
    assert _matches_any_secret_pattern("ghp_" + "a" * 36) is True
    assert _matches_any_secret_pattern("AKIA" + "A" * 16) is True
    assert _matches_any_secret_pattern("user-theme") is False
    assert _matches_any_secret_pattern(42) is False


def test_safe_key_denylist_no_longer_contains_key() -> None:
    """'key' and 'keys' must NOT be in _SAFE_KEY_DENYLIST."""
    from allbrain.security.redaction import _SAFE_KEY_DENYLIST

    assert "key" not in _SAFE_KEY_DENYLIST
    assert "keys" not in _SAFE_KEY_DENYLIST


def test_fp_task_key_still_not_masked() -> None:
    """task_key, foreign_key etc. must still be in denylist."""
    result = sanitize_payload({"task_key": "tk-123", "foreign_key": "fk-9"})
    assert result["task_key"] == "tk-123"
    assert result["foreign_key"] == "fk-9"


# ---------------------------------------------------------------------------
# Step 4: iter_events_through_cursor generator
# ---------------------------------------------------------------------------


def test_iter_events_through_cursor_yields_all_events(tmp_path: Path) -> None:
    """iter_events_through_cursor must yield the same events as load_events_through_cursor."""
    from allbrain.server.tools._shared import iter_events_through_cursor, load_events_through_cursor

    repo, project_root = make_repo(tmp_path)
    session_id = repo.create_session(project_root, "test").id or 0
    for i in range(25):
        repo.append_event(
            project_path=project_root,
            session_id=session_id,
            type="file_modified",
            source="test",
            payload={"index": i},
            file_path=f"file_{i}.py",
        )

    as_list = load_events_through_cursor(repo, project_path=project_root, batch_size=10)
    as_gen = list(iter_events_through_cursor(repo, project_path=project_root, batch_size=10))

    assert len(as_list) == len(as_gen) == 25
    assert [e.id for e in as_list] == [e.id for e in as_gen]


def test_iter_events_through_cursor_is_lazy(tmp_path: Path) -> None:
    """iter_events_through_cursor should not materialize everything upfront."""
    from allbrain.server.tools._shared import iter_events_through_cursor

    repo, project_root = make_repo(tmp_path)
    session_id = repo.create_session(project_root, "test").id or 0
    for i in range(20):
        repo.append_event(
            project_path=project_root,
            session_id=session_id,
            type="file_modified",
            source="test",
            payload={"index": i},
            file_path=f"file_{i}.py",
        )

    gen = iter_events_through_cursor(repo, project_path=project_root, batch_size=10)
    assert hasattr(gen, "__next__")  # generator, not list


# ---------------------------------------------------------------------------
# Step 5: threading.Event().wait() in open_write_session
# ---------------------------------------------------------------------------


def test_open_write_session_uses_threading_event() -> None:
    """Verify open_write_session uses threading.Event().wait() for backoff."""
    import inspect

    import allbrain.storage.database as db_mod

    source = inspect.getsource(db_mod.open_write_session)
    assert "threading.Event().wait(delay)" in source
    assert "time.sleep" not in source
