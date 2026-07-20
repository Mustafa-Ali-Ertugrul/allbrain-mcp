from __future__ import annotations

from pathlib import Path

from allbrain.contradiction import ContradictionDetector
from allbrain.domains.reasoning.intent import IntentExtractor, IntentStore
from allbrain.resume import IncrementalResumeEngine, IntentResumeEngine, MultiAgentResumeEngine
from allbrain.server.tools.events import save_event_impl
from allbrain.server.tools.intents import (
    detect_contradictions_impl,
    extract_intents_impl,
)
from allbrain.server.tools.intents import register_tools as register_intent_tools
from allbrain.server.tools.snapshots import (
    create_snapshot_impl,
    resume_with_intent_impl,
)
from allbrain.storage import BrainRepository, SnapshotRepo
from tests._helpers import make_context_from_repo, make_repo


class ToolRegistry:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, function):
        self.tools[function.__name__] = function
        return function


def test_intent_extractor_maps_semantic_events_and_ignores_tool_call(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(context, type="task_started", payload={"task": "JWT"})
    save_event_impl(context, type="file_modified", payload={}, file_path="auth.py")
    save_event_impl(context, type="failure", payload={"error": "bad"})
    save_event_impl(context, type="task_completed", payload={"task": "JWT"})

    events = repo.list_events(project_path=project_root)
    intents = IntentExtractor().extract(events)

    assert [intent.sub_goal for intent in intents] == [
        "task_started",
        "failure",
        "task_completed",
    ]
    assert [intent.status for intent in intents] == [
        "completed",
        "active",
        "completed",
    ]
    assert all(intent.agent_id == "codex" for intent in intents)
    assert intents[0].confidence > 0.7
    assert intents[0].related_files == ["auth.py"]


def test_intent_graph_links_shared_file_same_task_and_caused_by_lineage(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")
    parent = save_event_impl(context, type="task_started", payload={"task": "JWT"})
    save_event_impl(context, type="task_blocked", payload={"task": "JWT"}, caused_by=parent.data["id"])
    save_event_impl(context, type="task_completed", payload={"task": "JWT"})
    save_event_impl(context, type="file_modified", payload={}, file_path="auth.py")
    save_event_impl(context, type="file_modified", payload={}, file_path="auth.py")

    events = repo.list_events(project_path=project_root)
    intents = IntentExtractor().extract(events)
    graph = IntentStore().build_graph(intents, events).to_dict()

    edge_count = sum(len(edges) for edges in graph["edges"].values())
    edge_types = {edge["edge_type"] for edges in graph["edges"].values() for edge in edges}
    assert len(graph["nodes"]) == 5
    assert edge_count >= 2
    assert {"same_file", "same_task", "caused_by"} <= edge_types


def test_contradiction_detector_flags_different_goals_on_shared_file(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    save_event_impl(
        make_context_from_repo(repo, project_root, "codex"),
        type="task_started",
        payload={"task": "JWT refactor"},
        file_path="auth.py",
    )
    save_event_impl(
        make_context_from_repo(repo, project_root, "claude"),
        type="task_started",
        payload={"task": "Auth cleanup"},
        file_path="auth.py",
    )

    intents = IntentExtractor().extract(repo.list_events(project_path=project_root))
    contradictions = ContradictionDetector().detect(intents)

    assert contradictions
    assert contradictions[0]["severity"] == "warning"
    assert contradictions[0]["severity_score"] == 50
    assert contradictions[0]["related_files"] == ["auth.py"]


def test_contradiction_detector_ignores_same_agent_and_same_goal(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(codex, type="task_started", payload={"task": "JWT"}, file_path="auth.py")
    save_event_impl(codex, type="task_started", payload={"task": "Auth cleanup"}, file_path="auth.py")
    save_event_impl(
        make_context_from_repo(repo, project_root, "claude"),
        type="task_started",
        payload={"task": "JWT"},
        file_path="middleware.py",
    )

    intents = IntentExtractor().extract(repo.list_events(project_path=project_root))

    assert ContradictionDetector().detect(intents) == []


def test_resume_with_intent_contradiction_overrides_next_step(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    save_event_impl(
        make_context_from_repo(repo, project_root, "codex"),
        type="task_started",
        payload={"task": "JWT refactor"},
        file_path="auth.py",
    )
    save_event_impl(
        make_context_from_repo(repo, project_root, "claude"),
        type="task_started",
        payload={"task": "Auth cleanup"},
        file_path="auth.py",
    )

    result = resume_with_intent_impl(
        make_context_from_repo(repo, project_root, "opencode"), include_git=False, use_snapshot=False
    )

    assert result.ok
    assert result.data["contradiction_view"]["count"] == 1
    assert result.data["decision_view"]["next_step"] == "resolve contradiction in auth.py"


def test_resume_with_intent_continues_latest_intent_without_contradiction(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(codex, type="task_started", payload={"task": "JWT refactor"})
    save_event_impl(codex, type="file_modified", payload={}, file_path="auth.py")

    claude = make_context_from_repo(repo, project_root, "claude")
    result = resume_with_intent_impl(claude, include_git=False, use_snapshot=False)

    assert result.ok
    assert result.data["contradiction_view"]["count"] == 0
    assert result.data["decision_view"]["next_step"] == "continue intent: JWT refactor"


def test_intent_mcp_tools_return_intents_and_contradictions(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    save_event_impl(
        make_context_from_repo(repo, project_root, "codex"),
        type="task_started",
        payload={"task": "JWT refactor"},
        file_path="auth.py",
    )
    save_event_impl(
        make_context_from_repo(repo, project_root, "claude"),
        type="task_started",
        payload={"task": "Auth cleanup"},
        file_path="auth.py",
    )
    context = make_context_from_repo(repo, project_root, "codex")

    intents = extract_intents_impl(context)
    contradictions = detect_contradictions_impl(context)

    assert intents.ok
    assert intents.data["count"] == 2
    assert contradictions.ok
    assert contradictions.data["count"] == 1


def test_registered_intent_tools_use_bound_project_context(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")
    registry = ToolRegistry()
    register_intent_tools(registry, context)

    assert registry.tools["extract_intents"]()["ok"] is True
    assert registry.tools["extract_intents"](10)["ok"] is True
    assert registry.tools["detect_contradictions"]()["ok"] is True
    assert registry.tools["detect_contradictions"](10)["ok"] is True


def test_intent_impl_ignores_per_call_project_override(tmp_path: Path) -> None:
    """Legacy project_path kwargs are stripped; binding stays on BrainContext."""
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")

    intents = extract_intents_impl(context, project_path=str(tmp_path / "other"))
    contradictions = detect_contradictions_impl(context, project_path=str(tmp_path / "other"))

    assert intents.ok is True, intents.error
    assert contradictions.ok is True, contradictions.error


def test_snapshot_v7_stores_intent_and_contradiction_summaries(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(context, type="task_started", payload={"task": "JWT refactor"}, file_path="auth.py")
    save_event_impl(
        make_context_from_repo(repo, project_root, "claude"),
        type="task_started",
        payload={"task": "Auth cleanup"},
        file_path="auth.py",
    )

    snapshot = create_snapshot_impl(context, force=True, include_derived=True)

    assert snapshot.ok
    assert snapshot.data["metadata"]["snapshot_schema_version"] == "7.2"
    assert snapshot.data["state"]["intent_view"]["active_intents"] == 2
    assert snapshot.data["state"]["contradiction_view"]["count"] == 1


def test_v4_snapshot_adapter_adds_empty_intent_defaults(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(context, type="task_started", payload={"task": "JWT"})
    project = repo.get_project_by_path(project_root)
    assert project is not None
    SnapshotRepo(repo.engine).save(
        project_id=project.id or 0,
        event_cursor=None,
        state={
            "global_view": {},
            "agent_view": [],
            "conflict_view": {"conflicts": [], "count": 0},
            "decision_view": {},
        },
        metadata={"snapshot_schema_version": "4.0", "reducer_version": "4.0", "compression_version": "1.1"},
    )

    result = resume_with_intent_impl(context, include_git=False, use_snapshot=True)

    assert result.ok
    assert result.data["global_state"]["snapshot_used"] is True


def test_intent_drift_collapses_file_churn_into_main_task_intent(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(context, type="task_started", payload={"task": "JWT refactor"})
    for index in range(50):
        save_event_impl(context, type="file_modified", payload={}, file_path=f"auth_{index % 3}.py")
    save_event_impl(context, type="task_completed", payload={"task": "JWT refactor"})

    intents = IntentExtractor().extract(repo.list_events(project_path=project_root, limit=200))

    assert len(intents) == 2
    assert intents[0].goal == "JWT refactor"
    assert intents[0].status == "completed"
    assert set(intents[0].related_files) == {"auth_0.py", "auth_1.py", "auth_2.py"}
    assert intents[0].confidence > 0.7


def test_contradiction_false_positive_refactor_plus_tests_is_supportive(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    save_event_impl(
        make_context_from_repo(repo, project_root, "codex"),
        type="task_started",
        payload={"task": "refactor auth.py"},
        file_path="auth.py",
    )
    save_event_impl(
        make_context_from_repo(repo, project_root, "claude"),
        type="task_started",
        payload={"task": "add tests for auth.py"},
        file_path="auth.py",
    )

    intents = IntentExtractor().extract(repo.list_events(project_path=project_root))

    assert ContradictionDetector().detect(intents) == []


def test_snapshot_delta_intent_replay_equals_full_replay_for_graph_contradictions_and_decision(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex")
    save_event_impl(codex, type="task_started", payload={"task": "JWT refactor"}, file_path="auth.py")
    create_snapshot_impl(codex, force=True)
    save_event_impl(
        make_context_from_repo(repo, project_root, "claude"),
        type="task_started",
        payload={"task": "Auth cleanup"},
        file_path="auth.py",
    )

    events = repo.list_events(project_path=project_root, limit=100)
    project = repo.get_project_by_path(project_root)
    assert project is not None
    incremental = IncrementalResumeEngine(repo, SnapshotRepo(repo.engine))
    intent_engine = IntentResumeEngine(MultiAgentResumeEngine(incremental))
    full = intent_engine.resume(
        events=events,
        project_path=str(project_root),
        project_id=project.id or 0,
        limit=100,
        include_git=False,
        use_snapshot=False,
    )
    restored = intent_engine.resume(
        events=events,
        project_path=str(project_root),
        project_id=project.id or 0,
        limit=100,
        include_git=False,
        use_snapshot=True,
    )

    assert restored["intent_graph"] == full["intent_graph"]
    assert restored["contradiction_view"] == full["contradiction_view"]
    assert restored["decision_view"] == full["decision_view"]

