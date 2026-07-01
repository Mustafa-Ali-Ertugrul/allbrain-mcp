from __future__ import annotations

from pathlib import Path

from allbrain.events import EventType
from allbrain.graph import GraphQueryEngine, WorkflowGraphBuilder
from allbrain.metrics import AdvancedMetrics, AgentRanking
from allbrain.observability import SpanExporter, Tracer
from allbrain.replay import EventReplayEngine, FailureAnalyzer
from allbrain.server import BrainContext
from allbrain.server.app import (
    get_system_metrics_impl,
    get_workflow_graph_impl,
    get_workflow_trace_impl,
    replay_workflow_impl,
    save_event_impl,
)
from tests._helpers import make_context


def seed_trace_events(context: BrainContext) -> None:
    assert save_event_impl(
        context,
        type=EventType.TASK_CREATED.value,
        payload={"task_id": "wf1", "workflow_id": "wf1", "goal": "Build feature"},
    ).ok
    assert save_event_impl(
        context,
        type=EventType.TASK_ASSIGNED.value,
        payload={"task_id": "wf1", "workflow_id": "wf1", "agent_id": "builder", "breakdown": {}},
        agent_id="builder",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.SELECTION_DECISION.value,
        payload={
            "task_id": "wf1",
            "workflow_id": "wf1",
            "agent_id": "builder",
            "total_score": 0.8,
            "breakdown": {"capability": 1.0},
        },
        agent_id="builder",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.AGENT_EXECUTION_STARTED.value,
        payload={"task_id": "wf1", "workflow_id": "wf1", "node_id": "n1", "agent_id": "builder"},
        agent_id="builder",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.AGENT_EXECUTION_FAILED.value,
        payload={
            "task_id": "wf1",
            "workflow_id": "wf1",
            "node_id": "n1",
            "agent_id": "builder",
            "duration_ms": 250,
            "cost_usd": 0.03,
            "error": "timeout",
        },
        agent_id="builder",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.TASK_FAILED.value,
        payload={"task_id": "wf1", "workflow_id": "wf1", "reason": "timeout"},
        agent_id="builder",
    ).ok


def events(context: BrainContext):
    return context.repository.list_events(project_path=context.project_path, limit=5000)


def test_trace_builds_nested_spans_and_otel_export(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_trace_events(context)

    spans = Tracer().build_spans(events(context))
    tree = Tracer().trace_tree(events(context))
    otel = SpanExporter().to_otel(spans)

    assert any(span.kind == "workflow" for span in spans)
    assert any(span.kind == "task" and span.parent_span_id == "workflow:wf1" for span in spans)
    assert any(span.kind == "agent_execution" and span.latency_ms == 250 for span in spans)
    assert tree["children"]["task:wf1"]
    assert otel["resourceSpans"][0]["scopeSpans"][0]["spans"]


def test_replay_is_deterministic_and_cursor_resumable(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_trace_events(context)
    all_events = events(context)

    full = EventReplayEngine().replay(all_events)
    first = EventReplayEngine().replay(all_events, cursor=0, step_count=2)
    resumed = EventReplayEngine().replay(all_events, cursor=first["cursor"])
    repeated = EventReplayEngine().replay(all_events)

    assert full == repeated
    assert first["has_more"] is True
    assert resumed["final_state"]["tasks"]["wf1"]["status"] == "failed"


def test_failure_analyzer_finds_failed_agent_and_reason(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_trace_events(context)

    result = FailureAnalyzer().analyze(events(context))

    assert result["count"] == 2
    assert result["failures"][0]["agent_id"] == "builder"
    assert result["failures"][0]["reason"] == "timeout"


def test_graph_builder_queries_failed_paths_and_cost(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_trace_events(context)
    assert save_event_impl(
        context,
        type=EventType.TASK_DEPENDENCY_ADDED.value,
        payload={"task_id": "wf1", "workflow_id": "wf1", "depends_on": "root"},
    ).ok

    graph = WorkflowGraphBuilder().build(events(context))
    query = GraphQueryEngine(graph)

    assert graph["has_cycle"] is False
    assert any(edge["edge_type"] == "dependency" for edge in graph["edges"])
    assert query.find_paths(agent="builder", failed=True)
    assert query.get_cost_by_workflow("wf1") == 0.03
    assert query.most_expensive_agent() == {"agent_id": "builder", "cost_usd": 0.03}


def test_advanced_metrics_and_ranking(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_trace_events(context)

    metrics = AdvancedMetrics().build(events(context))
    ranking = AgentRanking().leaderboard(events(context))

    assert metrics["agents"]["builder"]["p95_latency_ms"] == 250
    assert metrics["agents"]["builder"]["cost_usd"] == 0.03
    assert ranking[0]["agent_id"] == "builder"


def test_sprint11_mcp_impls_return_stable_payloads(tmp_path: Path) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=10_000)
    seed_trace_events(context)

    trace = get_workflow_trace_impl(context, workflow_id="wf1")
    replay = replay_workflow_impl(context, workflow_id="wf1", cursor=0, step_count=3)
    graph = get_workflow_graph_impl(context, workflow_id="wf1")
    metrics = get_system_metrics_impl(context)

    assert trace.ok and trace.data["trace"]["spans"]
    assert replay.ok and replay.data["replay"]["frames"]
    assert graph.ok and graph.data["graph"]["nodes"]
    assert metrics.ok and metrics.data["agent_ranking"]
