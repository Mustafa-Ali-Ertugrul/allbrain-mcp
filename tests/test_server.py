from pathlib import Path

from allbrain.server.tools.events import (
    list_events_impl,
    save_event_impl,
)
from allbrain.server.tools.git import (
    get_git_context_impl,
    get_git_status_impl,
    get_recent_changes_impl,
)
from allbrain.server.tools.snapshots import resume_project_impl
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from tests._helpers import make_context, make_context_from_repo


def test_save_event_binds_active_session_and_audits_tool_call(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    result = save_event_impl(
        context,
        type="file_modified",
        payload={"file": "auth.py"},
        source="agent",
    )

    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    assert [event.type for event in events] == ["file_modified", "tool_call"]
    assert events[0].session_id == context.active_session_id
    assert events[1].payload["tool_name"] == "save_event"


def test_save_event_rejects_non_dict_payload(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    result = save_event_impl(context, type="file_modified", payload="bad")

    assert not result.ok
    assert "payload" in (result.error or "")


def test_save_event_rejects_importance_outside_range(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    result = save_event_impl(context, type="file_modified", payload={}, importance=6)

    assert not result.ok
    assert "importance" in (result.error or "")


def test_save_event_rejects_unknown_event_type(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    result = save_event_impl(context, type="mystery", payload={})

    assert not result.ok
    assert "unknown event type" in (result.error or "")


def test_save_event_requires_active_session_when_session_id_missing(tmp_path: Path) -> None:
    context = make_context(tmp_path, active=False)

    result = save_event_impl(context, type="file_modified", payload={})

    assert not result.ok
    assert "No active session" in (result.error or "")


def test_list_events_audits_tool_call(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    save_event_impl(context, type="file_modified", payload={"file": "auth.py"})

    result = list_events_impl(context, limit=10)

    assert result.ok
    all_events = context.repository.list_events(project_path=context.project_path)
    assert [event.type for event in all_events] == ["file_modified", "tool_call", "tool_call"]


def test_resume_project_builds_state_and_keeps_tool_usage_secondary(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    save_event_impl(context, type="goal_set", payload={"goal": "JWT Refactor"})
    save_event_impl(context, type="task_started", payload={"task": "Update middleware"})
    save_event_impl(context, type="file_modified", payload={}, file_path="middleware.py")

    result = resume_project_impl(context, detail="full", include_git=False)

    assert result.ok
    data = result.data
    assert data["goal"] == "JWT Refactor"
    assert data["open_tasks"] == ["Update middleware"]
    assert data["working_files"] == ["middleware.py"]
    assert data["next_step"] == "Continue task: Update middleware"
    assert [tool["tool_name"] for tool in data["tool_usage"]] == [
        "save_event",
        "save_event",
        "save_event",
    ]
    all_events = context.repository.list_events(project_path=context.project_path)
    assert all_events[-1].type == "tool_call"
    assert all_events[-1].payload["tool_name"] == "resume_project"


def test_resume_project_scores_blocker_over_open_task(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    save_event_impl(context, type="task_started", payload={"task": "Update middleware"})
    save_event_impl(context, type="task_blocked", payload={"reason": "Redis unavailable"})

    result = resume_project_impl(context, detail="full", include_git=False)

    assert result.ok
    assert result.data["next_step"] == "Resolve blockers first"


def test_git_tools_are_safe_outside_git_repo(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    git_context = get_git_context_impl(context)
    git_status = get_git_status_impl(context)
    recent_changes = get_recent_changes_impl(context, limit=5)

    assert git_context.ok
    assert git_context.data["is_repo"] is False
    assert git_context.data["normalized"] == {"intent": "unknown", "risk": "low", "files": []}
    assert git_status.ok
    assert git_status.data["is_repo"] is False
    assert recent_changes.ok
    assert recent_changes.data == []


def test_quality_gate_event_consistency_resume_state_is_stable(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    save_event_impl(context, type="task_started", payload={"task": "JWT Refactor"})
    save_event_impl(context, type="file_modified", payload={}, file_path="auth.py")
    save_event_impl(context, type="file_modified", payload={}, file_path="middleware.py")
    save_event_impl(context, type="failure", payload={"error": "Redis limiter failed"})
    save_event_impl(context, type="task_completed", payload={"task": "JWT Refactor"})

    events = context.repository.list_events(project_path=context.project_path)
    event_ids = [event.id for event in events]
    assert event_ids == sorted(event_ids)
    assert [event.type for event in events] == [
        "task_started",
        "tool_call",
        "file_modified",
        "tool_call",
        "file_modified",
        "tool_call",
        "failure",
        "tool_call",
        "task_completed",
        "tool_call",
    ]

    result = resume_project_impl(context, detail="full", include_git=False)

    assert result.ok
    data = result.data
    assert data["open_tasks"] == []
    assert data["completed"] == ["JWT Refactor"]
    assert data["working_files"] == ["auth.py", "middleware.py"]
    assert data["failures"] == [{"error": "Redis limiter failed"}]
    assert data["next_step"] == "Investigate the latest failure"
    assert len(data["tool_usage"]) == 5
    assert len(data["completed"]) == len(set(data["completed"]))
    assert len(data["working_files"]) == len(set(data["working_files"]))


def test_quality_gate_agent_switch_simulation_reconstructs_context(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()

    codex_context = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(codex_context, type="task_started", payload={"task": "Migrate middleware"})
    save_event_impl(codex_context, type="file_modified", payload={}, file_path="middleware.py")
    save_event_impl(codex_context, type="failure", payload={"error": "Redis limiter failed"})

    claude_context = make_context_from_repo(repo, project_root, "claude")
    result = resume_project_impl(claude_context, detail="full", include_git=False)

    assert result.ok
    data = result.data
    assert data["open_tasks"] == ["Migrate middleware"]
    assert data["working_files"] == ["middleware.py"]
    assert data["failures"] == [{"error": "Redis limiter failed"}]
    assert data["next_step"] == "Investigate the latest failure"
    assert [tool["tool_name"] for tool in data["tool_usage"]] == [
        "save_event",
        "save_event",
        "save_event",
    ]


def test_middleware_result_outcome_extracts_from_dict_correctly() -> None:
    from allbrain.server.lifecycle_middleware import _result_outcome

    # Dict with ok=True
    ok, error = _result_outcome({"ok": True, "data": "yes"})
    assert ok is True
    assert error is None

    # Dict with ok=False
    ok, error = _result_outcome({"ok": False, "error": "failed"})
    assert ok is False
    assert error == "failed"

    # Fallback to model object
    class DummyResult:
        is_error = True
        structured_content = None

    ok, error = _result_outcome(DummyResult())
    assert ok is False
    assert error == "MCP tool result marked as error"
