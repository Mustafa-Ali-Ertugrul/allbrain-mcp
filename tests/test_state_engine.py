from datetime import datetime, timezone

from allbrain.core import StateEngine
from allbrain.models.schemas import EventRead
from allbrain.resume import ResumeEngine


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
        created_at=datetime.now(timezone.utc),
    )


def test_state_engine_keeps_tool_usage_without_mutating_task_state() -> None:
    events = [
        make_event("1", "task_started", {"task": "JWT Refactor"}),
        make_event("2", "tool_call", {"tool_name": "list_events", "tool_args": {}, "timestamp": "now"}),
        make_event("3", "file_modified", {}, file_path="auth.py"),
    ]

    state = StateEngine().build_state({"events": events, "git": {}})

    assert state["open_tasks"] == ["JWT Refactor"]
    assert state["working_files"] == ["auth.py"]
    assert state["tool_usage"][0]["event_id"] == "2"
    assert state["last_event_id"] == "3"


def test_resume_engine_scores_failure_over_file_fallback() -> None:
    events = [
        make_event("1", "file_modified", {}, file_path="auth.py"),
        make_event("2", "failure", {"error": "Redis limiter failed"}),
    ]

    result = ResumeEngine().resume(events=events, project_path=".", include_git=False)

    assert result["next_step"] == "Investigate the latest failure"


def test_quality_gate_state_machine_integrity_restart_same_task() -> None:
    events = [
        make_event("1", "task_started", {"task": "JWT Refactor"}),
        make_event("2", "task_completed", {"task": "JWT Refactor"}),
        make_event("3", "task_started", {"task": "JWT Refactor"}),
    ]

    result = ResumeEngine().resume(events=events, project_path=".", include_git=False)

    assert result["open_tasks"] == ["JWT Refactor"]
    assert result["completed"] == ["JWT Refactor"]
    assert result["next_step"] == "Continue task: JWT Refactor"


def test_quality_gate_next_step_scores_blocker_over_all_other_signals() -> None:
    events = [
        make_event("1", "task_started", {"task": "Update middleware"}),
        make_event("2", "file_modified", {}, file_path="middleware.py"),
        make_event("3", "failure", {"error": "Redis limiter failed"}),
        make_event("4", "task_blocked", {"reason": "Redis unavailable"}),
    ]

    result = ResumeEngine().resume(events=events, project_path=".", include_git=False)

    assert result["next_step"] == "Resolve blockers first"
    assert result["open_tasks"] == ["Update middleware"]
    assert result["working_files"] == ["middleware.py"]
    assert result["failures"] == [{"error": "Redis limiter failed"}]
    assert result["blocked"] == [{"reason": "Redis unavailable"}]


def test_apply_events_uses_explicit_merge_strategy() -> None:
    base = {
        "goal": "Base goal",
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
        make_event("3", "file_modified", {}, file_path="auth.py"),
        make_event("4", "file_modified", {}, file_path="middleware.py"),
        make_event("5", "failure", {"error": "new"}),
    ]

    state = StateEngine().apply_events(base, events, git={})

    assert state["working_files"] == ["auth.py", "middleware.py"]
    assert state["open_tasks"] == ["Old task", "New task"]
    assert state["completed_tasks"] == ["Done task"]
    assert state["failures"] == [{"error": "old"}, {"error": "new"}]
    assert state["event_count"] == 14


def test_state_machine_idempotent_under_duplicated_events() -> None:
    from allbrain.core.state_machine import StateMachine

    failure_event = make_event("evt-fail-1", "failure", {"error": "boom"})
    tool_event = make_event("evt-tool-1", "tool_call", {"tool_name": "search", "tool_args": {}, "timestamp": "t0"})

    machine = StateMachine()
    machine.apply(failure_event)
    machine.apply(tool_event)
    machine.apply(failure_event)
    machine.apply(tool_event)

    state = machine.get_state()
    assert len(state.failures) == 1
    assert len(state.tool_usage) == 1
    assert state.tool_usage[0]["event_id"] == "evt-tool-1"
