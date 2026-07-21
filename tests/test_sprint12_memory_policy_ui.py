from __future__ import annotations

from pathlib import Path

from allbrain.domains.governance.policy import RoutingEngine
from allbrain.domains.memory.memory import MemoryBuilder, MemoryRetriever, SemanticMemory
from allbrain.domains.memory.ui import GraphExplorer, MetricsDashboard, ReplayViewer, TraceViewer
from allbrain.events import EventType
from allbrain.server import BrainContext
from allbrain.server.tools.events import save_event_impl
from allbrain.server.tools.knowledge import recommend_policy_impl
from allbrain.server.tools.memory import (
    build_memory_impl,
    retrieve_memory_impl,
)
from allbrain.server.tools.ui import (
    get_ui_graph_view_impl,
    get_ui_metrics_view_impl,
    get_ui_replay_view_impl,
    get_ui_trace_view_impl,
)
from tests._helpers import make_context


def seed_memory_events(context: BrainContext) -> None:
    assert save_event_impl(
        context,
        type=EventType.TASK_CREATED.value,
        payload={"task_id": "task_auth", "workflow_id": "wf_auth", "goal": "Security review auth flow"},
    ).ok
    assert save_event_impl(
        context,
        type=EventType.TASK_ASSIGNED.value,
        payload={"task_id": "task_auth", "workflow_id": "wf_auth", "agent_id": "builder", "breakdown": {}},
        agent_id="builder",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.TASK_FAILED.value,
        payload={"task_id": "task_auth", "workflow_id": "wf_auth", "reason": "timeout"},
        agent_id="builder",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.TASK_ASSIGNED.value,
        payload={"task_id": "task_auth", "workflow_id": "wf_auth", "agent_id": "reviewer", "breakdown": {}},
        agent_id="reviewer",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.AGENT_EXECUTION_COMPLETED.value,
        payload={
            "task_id": "task_auth",
            "workflow_id": "wf_auth",
            "node_id": "n1",
            "agent_id": "reviewer",
            "duration_ms": 120,
            "cost_usd": 0.02,
        },
        agent_id="reviewer",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.TASK_COMPLETED.value,
        payload={"task_id": "task_auth", "workflow_id": "wf_auth"},
        agent_id="reviewer",
    ).ok


def events(context: BrainContext):
    return context.repository.list_events(project_path=context.project_path, limit=5000)


def test_semantic_memory_embedding_is_deterministic() -> None:
    semantic = SemanticMemory()

    assert semantic.embed("Security review auth flow") == semantic.embed("Security review auth flow")


def test_memory_builder_and_retriever_rank_similar_workflows_and_failures(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_memory_events(context)
    items = MemoryBuilder().build(events(context))
    retriever = MemoryRetriever(items)

    similar = retriever.retrieve_similar_workflows("auth security review", top_k=1)
    failures = retriever.retrieve_failure_patterns("timeout", top_k=1)

    assert any(item.tags["kind"] == "workflow" for item in items)
    assert any(item.tags["kind"] == "failure_pattern" for item in items)
    assert any(item.tags["kind"] == "fallback_pattern" for item in items)
    assert similar[0]["id"] == "workflow:task_auth"
    assert failures[0]["tags"]["reason"] == "timeout"


def test_policy_is_advisory_and_prefers_successful_fallback_agent(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_memory_events(context)
    memory = MemoryRetriever(MemoryBuilder().build(events(context)))

    result = RoutingEngine().recommend(
        task={"goal": "Security review auth flow", "kind": "review"},
        events=events(context),
        memory=memory,
    )

    assert result["mode"] == "advisory"
    assert result["recommended_agent"] == "reviewer"
    assert "builder -> reviewer" in result["policy_signals"]["fallback_pairs"]
    assert result["confidence_level"] in {"low", "medium", "high"}


def test_ui_view_models_are_frontend_ready(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_memory_events(context)
    all_events = events(context)

    trace = TraceViewer().build(all_events)
    replay = ReplayViewer().build(all_events, cursor=0, step_count=2)
    graph = GraphExplorer().build(all_events)
    metrics = MetricsDashboard().build(all_events)

    assert trace["rows"]
    assert trace["timeline"]
    assert "total_cost_usd" in trace["cost_overlay"]
    assert replay["frames"]
    assert replay["current_state"]
    assert replay["diff_highlights"] == []
    assert graph["nodes"]
    assert graph["path_traces"]
    assert any(node["event_details"] for node in graph["nodes"])
    assert all("click" in node for node in graph["nodes"])
    assert metrics["leaderboard"][0]["agent_id"] == "reviewer"


def test_sprint12_mcp_impls_return_stable_json_payloads(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_memory_events(context)

    memory = build_memory_impl(context)
    retrieved = retrieve_memory_impl(context, query="auth security", top_k=2)
    policy = recommend_policy_impl(context, task={"goal": "Security review auth flow", "kind": "review"})
    trace = get_ui_trace_view_impl(context, workflow_id="wf_auth")
    replay = get_ui_replay_view_impl(context, workflow_id="wf_auth", cursor=0, step_count=2)
    graph = get_ui_graph_view_impl(context, workflow_id="wf_auth")
    metrics = get_ui_metrics_view_impl(context)

    assert memory.ok and memory.data["items"]
    assert retrieved.ok and retrieved.data["similar_workflows"]
    assert policy.ok and policy.data["mode"] == "advisory"
    assert trace.ok and trace.data["rows"]
    assert replay.ok and replay.data["frames"]
    assert graph.ok and graph.data["nodes"]
    assert metrics.ok and metrics.data["leaderboard"]
