"""Regression tests for v0.2.4 fixes.

Covers:
- Step 1: StateEngine.apply_events() single-pass equivalence
- Step 2: QueueCoordinator.claim() uses open_write_session (concurrent safety)
- Step 3: _SAFE_KEY_DENYLIST value-based fallback
- Step 4: iter_events_through_cursor generator
- Step 5: open_write_session uses time.sleep for backoff
- Step 6: record_git_changes computes git fingerprint outside _session_lock
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

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

    for key in [
        "goal",
        "working_files",
        "open_tasks",
        "completed_tasks",
        "blocked",
        "failures",
        "tool_usage",
        "last_event_id",
        "last_working_file",
        "event_count",
        "git",
    ]:
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
    from allbrain.server.tools._events import iter_events_through_cursor, load_events_through_cursor

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
    from allbrain.server.tools._events import iter_events_through_cursor

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
# Step 5: open_write_session uses time.sleep for backoff
# ---------------------------------------------------------------------------


def test_open_write_session_uses_time_sleep() -> None:
    """Verify open_write_session uses time.sleep for backoff (honest, not misleading Event)."""
    import inspect

    import allbrain.storage.database as db_mod

    source = inspect.getsource(db_mod.open_write_session)
    assert "time.sleep(delay)" in source


# ---------------------------------------------------------------------------
# Step 2: QueueCoordinator.claim() uses open_write_session (concurrent safety)
# ---------------------------------------------------------------------------


def test_concurrent_claim_no_double_assignment(tmp_path: Path) -> None:
    """10 threads claiming concurrently must each win a distinct queued item.

    Step 2 switched ``claim()`` to ``open_write_session`` (BEGIN IMMEDIATE) so the
    conditional ``UPDATE ... WHERE state == 'queued'`` is atomic. Enqueue 5 items
    for one agent; concurrent claims must yield exactly 5 distinct leases — no
    item claimed twice, no item lost.
    """
    from allbrain.server import BrainContext
    from allbrain.server.queueing import QueueCoordinator
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repository = BrainRepository(engine)
    project = tmp_path / "project"
    project.mkdir()
    project_path = str(project.resolve())
    session = repository.create_session(project, "codex", server_instance_id="instance-a")
    context = BrainContext(
        repository=repository,
        project_path=project_path,
        active_session=session,
        agent_name="codex",
        server_instance_id="instance-a",
    )
    coordinator = QueueCoordinator(context)

    n_tasks = 5
    for i in range(n_tasks):
        coordinator.enqueue_task(
            task_id=f"task-{i}",
            goal=f"goal-{i}",
            agent_id="codex",
            workflow_id="wf",
            node_id=f"node-{i}",
        )

    claimed_ids: list[str] = []
    barrier = threading.Barrier(10)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait()
            result = coordinator.claim(agent_id="codex", server_instance_id="instance-a")
            if result is not None:
                claimed_ids.append(result["queue_item_id"])
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent claim raised: {errors}"
    assert len(claimed_ids) == n_tasks, f"expected {n_tasks} distinct claims, got {len(claimed_ids)}"
    assert len(set(claimed_ids)) == n_tasks, "a queued item was assigned more than once"


# ---------------------------------------------------------------------------
# Step 6: record_git_changes computes git fingerprint outside _session_lock
# ---------------------------------------------------------------------------


def test_git_fingerprint_computed_outside_lock(tmp_path: Path) -> None:
    """build_fingerprint() (subprocess I/O) must run outside the session lock.

    Step 6 moved the expensive ``GitBrain.build_fingerprint()`` call out of the
    ``with context._session_lock:`` block. This asserts the fingerprint is built
    while the RLock is NOT held.
    """
    from allbrain.server import BrainContext
    from allbrain.server.lifecycle import ensure_session_started, record_git_changes
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repository = BrainRepository(engine)
    project = tmp_path / "project"
    project.mkdir()
    context = BrainContext(
        repository=repository,
        project_path=str(project.resolve()),
        agent_name="codex",
        server_instance_id="instance-a",
    )
    session = ensure_session_started(context)

    # Track lock acquisition depth without relying on RLock._is_owned(),
    # which is a CPython implementation detail absent on some builds.
    real_lock = context._session_lock
    lock_state = {"depth": 0}

    class _TrackingRLock:
        def __enter__(self):
            lock_state["depth"] += 1
            real_lock.__enter__()
            return self

        def __exit__(self, *exc):
            real_lock.__exit__(*exc)
            lock_state["depth"] -= 1
            return False

        def __getattr__(self, name):
            return getattr(real_lock, name)

    context._session_lock = _TrackingRLock()

    lock_held_at_fingerprint: list[bool] = []

    def fake_fingerprint(self):  # noqa: ANN001
        lock_held_at_fingerprint.append(lock_state["depth"] > 0)
        return {"is_repo": False, "head": None, "branch": None, "files": {}}

    def fake_changed_paths(self, baseline, final):  # noqa: ANN001
        return []

    with (
        patch("allbrain.gitbrain.parser.GitBrain.build_fingerprint", fake_fingerprint),
        patch("allbrain.gitbrain.parser.GitBrain.changed_paths_between", fake_changed_paths),
    ):
        record_git_changes(context, session, confidence="low")

    assert lock_held_at_fingerprint, "build_fingerprint was never called"
    assert lock_held_at_fingerprint == [False], (
        "build_fingerprint ran while _session_lock was held; it must run outside the lock"
    )
