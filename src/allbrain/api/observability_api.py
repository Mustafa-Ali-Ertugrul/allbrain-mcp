from __future__ import annotations

from typing import Any

from allbrain.graph import GraphQueryEngine, StateGraph, WorkflowGraphBuilder
from allbrain.metrics import AdvancedMetrics, AgentRanking
from allbrain.models.schemas import EventRead
from allbrain.observability import SpanExporter, Tracer
from allbrain.replay import EventReplayEngine, ExecutionVisualizer, FailureAnalyzer


class ObservabilityAPI:
    def workflow_trace(
        self,
        events: list[EventRead],
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        filtered = _filter_events(events, workflow_id=workflow_id, task_id=task_id)
        spans = Tracer().build_spans(filtered)
        return {
            "trace": Tracer().trace_tree(filtered),
            "exports": {
                "json": SpanExporter().to_json(spans),
                "otel": SpanExporter().to_otel(spans),
                "prometheus": SpanExporter().to_prometheus(spans),
            },
        }

    def system_metrics(self, events: list[EventRead]) -> dict[str, Any]:
        return {
            "advanced_metrics": AdvancedMetrics().build(events),
            "agent_ranking": AgentRanking().leaderboard(events),
        }

    def replay(
        self,
        events: list[EventRead],
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
        cursor: int = 0,
        step_count: int | None = None,
        deterministic: bool = True,
    ) -> dict[str, Any]:
        filtered = _filter_events(events, workflow_id=workflow_id, task_id=task_id)
        return {
            "replay": EventReplayEngine().replay(
                filtered,
                cursor=cursor,
                step_count=step_count,
                deterministic=deterministic,
            ),
            "visualization": ExecutionVisualizer().timeline(filtered),
            "failure_analysis": FailureAnalyzer().analyze(filtered),
        }

    def graph(
        self,
        events: list[EventRead],
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        filtered = _filter_events(events, workflow_id=workflow_id, task_id=task_id)
        graph = WorkflowGraphBuilder().build(filtered)
        query = GraphQueryEngine(graph)
        return {
            "graph": graph,
            "state_graph": StateGraph().build(filtered),
            "queries": {
                "failed_paths": query.find_paths(failed=True),
                "workflow_cost": query.get_cost_by_workflow(workflow_id or task_id or ""),
                "most_expensive_agent": query.most_expensive_agent(),
            },
        }


def _filter_events(
    events: list[EventRead],
    *,
    workflow_id: str | None = None,
    task_id: str | None = None,
) -> list[EventRead]:
    if workflow_id is None and task_id is None:
        return events
    return [
        event
        for event in events
        if (
            workflow_id is None
            or event.payload.get("workflow_id") == workflow_id
            or event.payload.get("root_task_id") == workflow_id
            or event.payload.get("task_id") == workflow_id
        )
        and (task_id is None or event.payload.get("task_id") == task_id)
    ]
