from datetime import UTC, datetime

from allbrain.core.state_engine import StateEngine
from allbrain.models.schemas import EventRead


def make_event(
    event_id: str,
    type: str,
    payload: dict,
    file_path: str | None = None,
) -> EventRead:
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


def test_apply_events_preserves_base_completed_tasks() -> None:
    base = {
        "goal": "Base goal",
        "working_files": ["auth.py"],
        "open_tasks": [],
        "completed_tasks": ["Done task"],
        "blocked": [{"reason": "old"}],
        "failures": [{"error": "old"}],
        "tool_usage": [{"tool_name": "old"}],
        "last_event_id": "1",
        "last_working_file": "auth.py",
        "event_count": 10,
        "git": {},
    }
    events = [
        make_event("2", "failure", {"error": "new"}),
        make_event("3", "task_completed", {"task": "New done"}),
    ]

    state = StateEngine().apply_events(base, events, git={})

    assert "Done task" in state["completed_tasks"]
    assert "New done" in state["completed_tasks"]
    assert state["failures"] == [{"error": "old"}, {"error": "new"}]
    assert state["blocked"] == [{"reason": "old"}]
    assert state["tool_usage"] == [{"tool_name": "old"}]
    assert state["event_count"] == 12


def test_apply_events_merges_open_tasks_with_base() -> None:
    base = {
        "goal": "Base",
        "working_files": [],
        "open_tasks": ["Old task"],
        "completed_tasks": [],
        "blocked": [],
        "failures": [],
        "tool_usage": [],
        "last_event_id": "1",
        "last_working_file": None,
        "event_count": 5,
        "git": {},
    }
    events = [make_event("2", "task_started", {"task": "New task"})]

    state = StateEngine().apply_events(base, events, git={})

    assert "Old task" in state["open_tasks"]
    assert "New task" in state["open_tasks"]
    assert state["event_count"] == 6


def test_apply_events_working_files_union_with_base() -> None:
    base = {
        "goal": None,
        "working_files": ["auth.py"],
        "open_tasks": [],
        "completed_tasks": [],
        "blocked": [],
        "failures": [],
        "tool_usage": [],
        "last_event_id": "1",
        "last_working_file": "auth.py",
        "event_count": 1,
        "git": {},
    }
    events = [
        make_event("2", "file_modified", {}, file_path="middleware.py"),
        make_event("3", "file_modified", {}, file_path="auth.py"),
    ]

    state = StateEngine().apply_events(base, events, git={})

    assert "auth.py" in state["working_files"]
    assert "middleware.py" in state["working_files"]
    assert state["last_working_file"] == "auth.py"
    assert state["event_count"] == 3


def test_apply_events_empty_events_returns_base_with_git() -> None:
    base = {
        "goal": "Base",
        "working_files": ["x.py"],
        "open_tasks": ["t1"],
        "completed_tasks": ["d1"],
        "blocked": [],
        "failures": [],
        "tool_usage": [],
        "last_event_id": "9",
        "last_working_file": "x.py",
        "event_count": 5,
        "git": {},
    }

    state = StateEngine().apply_events(base, [], git={"branch": "main"})

    assert state["git"] == {"branch": "main"}
    assert state["event_count"] == 5
    assert state["open_tasks"] == ["t1"]


def test_apply_events_single_machine_vs_two_machine_consistency() -> None:
    base = {
        "goal": "Base",
        "working_files": ["auth.py"],
        "open_tasks": ["Old task"],
        "completed_tasks": ["Done task"],
        "blocked": [{"reason": "old"}],
        "failures": [{"error": "old"}],
        "tool_usage": [{"tool_name": "old"}],
        "last_event_id": "1",
        "last_working_file": "auth.py",
        "event_count": 10,
        "git": {},
    }
    events = [
        make_event("2", "task_started", {"task": "New task"}),
        make_event("3", "failure", {"error": "new"}),
    ]

    state = StateEngine().apply_events(base, events, git={"branch": "main"})

    assert state["open_tasks"] == ["Old task", "New task"]
    assert state["failures"] == [{"error": "old"}, {"error": "new"}]
    assert state["completed_tasks"] == ["Done task"]
    assert state["tool_usage"] == [{"tool_name": "old"}]
    assert state["working_files"] == ["auth.py"]
    assert state["event_count"] == 12
    assert state["goal"] == "Base"
    assert state["git"] == {"branch": "main"}
