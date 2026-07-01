from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from allbrain.conflict import ConflictDetector, ConflictResolver
from allbrain.models.entities import Event
from allbrain.server.app import (
    detect_conflicts_impl,
    resolve_conflicts_impl,
    resume_project_impl,
    save_event_impl,
)
from allbrain.storage import (
    BrainRepository,
    SnapshotRepo,
    open_session,
)
from tests._helpers import make_context_from_repo, make_repo


def test_event_agent_attribution_and_branch_defaults(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")

    inherited = save_event_impl(context, type="file_modified", payload={}, file_path="auth.py")
    explicit = save_event_impl(
        context,
        type="file_modified",
        payload={},
        file_path="api.py",
        agent_id="claude",
        branch="claude-feature",
        impact_score=0.8,
    )

    assert inherited.ok
    assert explicit.ok
    events = repo.list_events(project_path=project_root, type="file_modified")
    assert events[0].agent_id == "codex"
    assert events[0].branch == "codex"
    assert events[1].agent_id == "claude"
    assert events[1].branch == "claude-feature"
    assert events[1].impact_score == 0.8


def test_event_graph_caused_by_validation(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")
    parent = save_event_impl(context, type="task_started", payload={"task": "JWT"})
    child = save_event_impl(context, type="file_modified", payload={}, file_path="auth.py", caused_by=parent.data["id"])
    invalid = save_event_impl(context, type="file_modified", payload={}, file_path="bad.py", caused_by="missing")

    assert child.ok
    assert child.data["caused_by"] == parent.data["id"]
    assert not invalid.ok
    assert "caused_by event missing" in (invalid.error or "")


def test_conflict_scoring_detects_close_file_conflict_but_not_far_or_same_agent(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex")
    claude = make_context_from_repo(repo, project_root, "claude")
    save_event_impl(codex, type="file_modified", payload={}, file_path="auth.py")
    save_event_impl(claude, type="file_modified", payload={}, file_path="auth.py")

    events = repo.list_events(project_path=project_root, type="file_modified")
    conflicts = ConflictDetector().detect(events)
    assert len(conflicts) == 1
    assert conflicts[0]["level"] == "L1"

    with open_session(repo.engine) as db:
        second = db.get(Event, events[1].id)
        assert second is not None
        second.created_at = second.created_at + timedelta(minutes=30)
        db.add(second)
        db.commit()
    far_events = repo.list_events(project_path=project_root, type="file_modified")
    assert ConflictDetector().detect(far_events) == []

    same_agent_context = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(same_agent_context, type="file_modified", payload={}, file_path="same.py")
    save_event_impl(same_agent_context, type="file_modified", payload={}, file_path="same.py")
    same_agent_events = [
        event
        for event in repo.list_events(project_path=project_root, type="file_modified")
        if event.file_path == "same.py"
    ]
    assert ConflictDetector().detect(same_agent_events) == []


def test_task_conflict_and_dynamic_resolution(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex")
    claude = make_context_from_repo(repo, project_root, "claude")
    save_event_impl(codex, type="task_started", payload={"task": "JWT"}, impact_score=0.2)
    save_event_impl(codex, type="failure", payload={"error": "bad"})
    save_event_impl(claude, type="task_started", payload={"task": "JWT"}, impact_score=0.9)
    save_event_impl(claude, type="task_completed", payload={"task": "JWT"}, impact_score=0.9)

    events = repo.list_events(project_path=project_root)
    conflicts = ConflictDetector().detect(events)
    resolved = ConflictResolver().resolve(
        conflicts,
        events,
        resume_project_impl(claude, include_git=False, use_snapshot=False).data["agent_view"],
    )

    assert any(conflict["level"] == "L2" for conflict in conflicts)
    assert any(item["winner_agent_id"] == "claude" for item in resolved if item["status"] == "resolved")


def test_multi_agent_resume_layered_output_and_conflict_first_decision(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    for agent in ["codex", "claude", "opencode"]:
        context = make_context_from_repo(repo, project_root, agent)
        save_event_impl(context, type="file_modified", payload={}, file_path="auth.py", impact_score=0.5)

    claude = make_context_from_repo(repo, project_root, "claude")
    result = resume_project_impl(claude, include_git=False, use_snapshot=False)

    assert result.ok
    data = result.data
    assert set(data) >= {"global_view", "agent_view", "conflict_view", "decision_view", "merged_state"}
    assert data["conflict_view"]["count"] >= 2
    assert data["decision_view"]["next_step"] == "resolve conflict in auth.py"
    assert data["next_step"] == "resolve conflict in auth.py"


def test_conflict_tools_return_detected_and_resolved_conflicts(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex")
    claude = make_context_from_repo(repo, project_root, "claude")
    save_event_impl(codex, type="file_modified", payload={}, file_path="auth.py")
    save_event_impl(claude, type="file_modified", payload={}, file_path="auth.py")
    context = make_context_from_repo(repo, project_root, "codex")

    detected = detect_conflicts_impl(context)
    resolved = resolve_conflicts_impl(context)

    assert detected.ok
    assert detected.data["count"] == 1
    assert resolved.ok
    assert resolved.data["count"] == 1


def test_v3_snapshot_adapter_maps_legacy_state(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(context, type="task_started", payload={"task": "JWT"})
    project = repo.get_project_by_path(project_root)
    assert project is not None
    SnapshotRepo(repo.engine).save(
        project_id=project.id or 0,
        event_cursor=None,
        state={
            "goal": None,
            "working_files": [],
            "open_tasks": ["JWT"],
            "completed_tasks": [],
            "blocked": [],
            "failures": [],
            "tool_usage": [],
            "last_event_id": None,
            "last_working_file": None,
            "event_count": 0,
            "git": {},
        },
        metadata={"snapshot_schema_version": "3.1", "reducer_version": "3.1", "compression_version": "1.1"},
    )

    result = resume_project_impl(context, include_git=False, use_snapshot=True)

    assert result.ok
    assert result.data["snapshot_used"] is True
    assert "global_view" in result.data


def test_resolver_does_not_pretend_to_resolve_low_margin_conflict(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    save_event_impl(
        make_context_from_repo(repo, project_root, "codex"),
        type="file_modified",
        payload={},
        file_path="auth.py",
        impact_score=0.5,
    )
    save_event_impl(
        make_context_from_repo(repo, project_root, "claude"),
        type="file_modified",
        payload={},
        file_path="auth.py",
        impact_score=0.5,
    )

    opencode = make_context_from_repo(repo, project_root, "opencode")
    result = resume_project_impl(opencode, include_git=False, use_snapshot=False)

    assert result.ok
    decision = result.data["decision_view"]
    assert decision["next_step"] == "resolve conflict in auth.py"
    assert decision["required_action"] == "manual_conflict_review"
    assert decision["confidence"] == 0.45
    assert any(item["status"] == "needs_review" for item in decision["resolved_conflicts"])


def test_conflict_aware_next_step_overrides_global_resume_next_step(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex")
    claude = make_context_from_repo(repo, project_root, "claude")
    save_event_impl(codex, type="failure", payload={"error": "Redis failed"})
    save_event_impl(codex, type="file_modified", payload={}, file_path="auth.py", impact_score=0.8)
    save_event_impl(claude, type="file_modified", payload={}, file_path="auth.py", impact_score=0.8)

    result = resume_project_impl(codex, include_git=False, use_snapshot=False)

    assert result.ok
    assert result.data["global_view"]["next_step"] == "Investigate the latest failure"
    assert result.data["decision_view"]["next_step"] == "resolve conflict in auth.py"
    assert result.data["next_step"] == "resolve conflict in auth.py"


def test_agent_switch_keeps_agent_views_and_global_context_aligned(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(codex, type="task_started", payload={"task": "JWT refactor"}, impact_score=0.6)
    save_event_impl(codex, type="file_modified", payload={}, file_path="auth.py", impact_score=0.6)

    claude = make_context_from_repo(repo, project_root, "claude")
    save_event_impl(claude, type="task_started", payload={"task": "middleware fix"}, impact_score=0.6)
    save_event_impl(claude, type="file_modified", payload={}, file_path="middleware.py", impact_score=0.6)

    opencode_resume = resume_project_impl(
        make_context_from_repo(repo, project_root, "opencode"), include_git=False, use_snapshot=False
    )

    assert opencode_resume.ok
    data = opencode_resume.data
    agent_by_id = {agent["agent_id"]: agent for agent in data["agent_view"]}
    assert agent_by_id["codex"]["current_task"] == "JWT refactor"
    assert agent_by_id["claude"]["current_task"] == "middleware fix"
    assert "auth.py" in data["global_view"]["working_files"]
    assert "middleware.py" in data["global_view"]["working_files"]
    assert data["conflict_view"]["count"] == 0
    assert data["decision_view"]["required_action"] == "continue"
