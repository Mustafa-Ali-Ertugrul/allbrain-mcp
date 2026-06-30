from pathlib import Path

from allbrain.events import EventType
from allbrain.server import BrainContext
from allbrain.server.app import (
    add_task_dependency_impl,
    assign_task_impl,
    change_task_priority_impl,
    create_snapshot_impl,
    create_task_impl,
    get_task_graph_impl,
    handoff_task_impl,
    orchestrate_project_impl,
    save_event_impl,
)
from allbrain.snapshot.versions import snapshot_versions
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def make_context(tmp_path: Path, agent: str = "codex") -> BrainContext:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, agent)
    return BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        active_session=session,
        auto_snapshot_threshold=10_000,
    )


def test_create_task_and_assignment_store_score_breakdown(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    created = create_task_impl(
        context,
        task_id="task_jwt",
        goal="JWT implementation",
        kind="implementation",
        related_files=["auth.py"],
        priority=3,
    )

    assigned = assign_task_impl(context, task_id="task_jwt")

    assert created.ok
    assert assigned.ok
    assignment = assigned.data["assignment"]
    assert assignment["agent_id"] == "codex"
    assert assignment["score"] == 0.7
    assert assignment["breakdown"]["capability"] == 1.0
    assert assignment["breakdown"]["success_rate"] == 0.5
    assert assignment["breakdown"]["metrics_confidence"] == 0.0
    assert assignment["breakdown"]["latency"] == 1.0
    assert assignment["breakdown"]["load"] == 1.0
    assert assignment["breakdown"]["cold_start_weighted"] is True
    event_payload = assigned.data["event"]["payload"]
    assert event_payload["breakdown"] == assignment["breakdown"]


def test_task_dependency_priority_queue_and_ownership_history_are_replayable(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    assert create_task_impl(context, task_id="task_a", goal="Auth refactor", kind="refactor", priority=2).ok
    assert create_task_impl(context, task_id="task_b", goal="JWT implementation", kind="implementation", priority=2).ok
    assert add_task_dependency_impl(context, task_id="task_b", depends_on="task_a").ok
    assert change_task_priority_impl(context, task_id="task_b", old=2, new=5).ok
    assert assign_task_impl(context, task_id="task_b", agent_id="codex").ok
    assert handoff_task_impl(context, task_id="task_b", from_agent="codex", to_agent="claude", reason="quota ended").ok

    graph = get_task_graph_impl(context, limit=100)

    assert graph.ok
    task_b = graph.data["task_view"]["tasks"]["task_b"]
    assert task_b["priority"] == 5
    assert task_b["owner"] == "claude"
    assert task_b["ownership_history"] == ["codex", "claude"]
    assert graph.data["task_view"]["agent_queue"] == {"claude": ["task_b"]}
    assert {"from": "task_a", "to": "task_b", "edge_type": "depends_on"} in graph.data["task_graph"]["edges"]


def test_orchestrator_recommends_handoff_for_blocked_task(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    assert create_task_impl(context, task_id="task_jwt", goal="JWT implementation", kind="reasoning", priority=5).ok
    assert assign_task_impl(context, task_id="task_jwt", agent_id="codex").ok
    assert save_event_impl(
        context,
        type="task_blocked",
        payload={"task_id": "task_jwt", "reason": "quota ended"},
        agent_id="codex",
    ).ok

    result = orchestrate_project_impl(context, include_git=False, limit=100)

    assert result.ok
    decision = result.data["decision_view"]
    assert decision["required_action"] == "handoff_task"
    assert decision["recommended_agent"] == "claude"
    assert decision["breakdown"]["capability"] == 1.0


def test_handoff_emits_handoff_and_assignment_events(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    assert create_task_impl(context, task_id="task_tests", goal="Write tests", kind="testing", priority=4).ok
    assert assign_task_impl(context, task_id="task_tests", agent_id="claude").ok

    handoff = handoff_task_impl(context, task_id="task_tests", from_agent="claude", reason="tests needed")

    assert handoff.ok
    assert handoff.data["handoff"]["to_agent"] == "opencode"
    assert handoff.data["handoff_event"]["type"] == "handoff_created"
    assert handoff.data["assigned_event"]["type"] == "task_assigned"
    assert handoff.data["assigned_event"]["payload"]["reason"] == "handoff"


def test_orchestrator_snapshot_v7_contains_task_layers(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    assert create_task_impl(context, task_id="task_jwt", goal="JWT implementation", kind="implementation").ok
    assert assign_task_impl(context, task_id="task_jwt").ok

    snapshot = create_snapshot_impl(context, force=True, limit=100)

    assert snapshot.ok
    for key, value in snapshot_versions().items():
        assert snapshot.data["metadata"][key] == value
    assert snapshot.data["state"]["task_view"]["tasks"]["task_jwt"]["owner"] == "codex"
    assert snapshot.data["state"]["assignment_view"]["agent_queue"] == {"codex": ["task_jwt"]}
    assert snapshot.data["state"]["agent_metrics"]["codex"]["assigned_count"] == 1
    assert snapshot.data["state"]["scheduler_state"]["agent_state"]["codex"]["current_load"] == 1


def test_audit_replay_determinism_full_replay_equals_snapshot_delta(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    agents = ["codex", "claude", "opencode"]
    session_id = context.active_session_id or 0

    for index in range(40):
        task_id = f"task_{index:03d}"
        agent_id = agents[index % len(agents)]
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.TASK_CREATED.value,
            source="test",
            payload={
                "task_id": task_id,
                "goal": f"Task {index}",
                "kind": "testing" if index % 3 == 0 else "implementation",
                "related_files": [f"module_{index % 7}.py"],
                "priority": (index % 5) + 1,
            },
            agent_id=agent_id,
        )
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.TASK_DEPENDENCY_ADDED.value,
            source="test",
            payload={"task_id": task_id, "depends_on": f"task_{index - 1:03d}" if index else "root"},
            agent_id=agent_id,
        )
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.TASK_ASSIGNED.value,
            source="test",
            payload={
                "task_id": task_id,
                "agent_id": agent_id,
                "score": 80,
                "breakdown": {"capability": 60, "availability": 20, "priority_bonus": 0},
            },
            agent_id=agent_id,
        )
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.TASK_STARTED.value,
            source="test",
            payload={"task_id": task_id, "task": f"Task {index}"},
            agent_id=agent_id,
        )
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.TASK_PRIORITY_CHANGED.value,
            source="test",
            payload={"task_id": task_id, "old": (index % 5) + 1, "new": 5 - (index % 5)},
            agent_id=agent_id,
        )

    snapshot = create_snapshot_impl(context, force=True, limit=1000)
    assert snapshot.ok

    for index in range(5):
        task_id = f"task_{index:03d}"
        from_agent = agents[index % len(agents)]
        to_agent = agents[(index + 1) % len(agents)]
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.TASK_BLOCKED.value,
            source="test",
            payload={"task_id": task_id, "reason": "agent switch audit"},
            agent_id=from_agent,
        )
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.HANDOFF_CREATED.value,
            source="test",
            payload={"task_id": task_id, "from_agent": from_agent, "to_agent": to_agent, "reason": "quota ended"},
            agent_id=from_agent,
        )
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.TASK_ASSIGNED.value,
            source="test",
            payload={
                "task_id": task_id,
                "agent_id": to_agent,
                "score": 90,
                "breakdown": {"capability": 60, "availability": 20, "priority_bonus": 10},
            },
            agent_id=to_agent,
        )
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=EventType.FILE_MODIFIED.value,
            source="test",
            payload={"task_id": task_id},
            file_path=f"module_{index}.py",
            agent_id=to_agent,
        )

    snapshot_delta = orchestrate_project_impl(context, include_git=False, use_snapshot=True, limit=1000)
    full_replay = orchestrate_project_impl(context, include_git=False, use_snapshot=False, limit=1000)

    assert snapshot_delta.ok
    assert full_replay.ok
    assert snapshot_delta.data["global_view"]["orchestrator_snapshot_used"] is True
    assert full_replay.data["global_view"]["orchestrator_snapshot_used"] is False
    for key in ["task_view", "task_graph", "assignment_view", "handoff_view", "decision_view", "scheduler_state"]:
        assert snapshot_delta.data[key] == full_replay.data[key]
