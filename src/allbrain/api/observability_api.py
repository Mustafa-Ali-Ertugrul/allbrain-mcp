from __future__ import annotations

from typing import Any

from allbrain.domains.analysis.graph.workflow_graph_builder import WorkflowGraphBuilder
from allbrain.observability import ObservabilityBuilder
from allbrain.replay.event_replay_engine import EventReplayEngine


class ObservabilityAPI:
    def replay(
        self,
        events: list[Any],
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
        cursor: int = 0,
        step_count: int | None = None,
        deterministic: bool = True,
    ) -> dict[str, Any]:
        filtered = events
        if workflow_id or task_id:
            filtered = [
                e
                for e in events
                if (
                    not workflow_id
                    or getattr(e, "payload", {}).get("workflow_id") == workflow_id
                    or getattr(e, "payload", {}).get("root_task_id") == workflow_id
                )
                and (not task_id or getattr(e, "payload", {}).get("task_id") == task_id)
            ]
        result = EventReplayEngine().replay(filtered, cursor=cursor, step_count=step_count, deterministic=deterministic)
        builder = ObservabilityBuilder()
        viz = builder.build(filtered)
        result["visualization"] = viz
        return result

    def workflow_trace(
        self,
        events: list[Any],
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        filtered = events
        if workflow_id or task_id:
            filtered = [
                e
                for e in events
                if (
                    not workflow_id
                    or getattr(e, "payload", {}).get("workflow_id") == workflow_id
                    or getattr(e, "payload", {}).get("root_task_id") == workflow_id
                )
                and (not task_id or getattr(e, "payload", {}).get("task_id") == task_id)
            ]
        dashboard = ObservabilityBuilder().build(filtered)
        return {
            "trace": dashboard["trace"],
            "exports": dashboard.get("exports", {}),
        }

    def system_metrics(self, events: list[Any]) -> dict[str, Any]:
        return ObservabilityBuilder().build(events)

    def graph(
        self,
        events: list[Any],
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        filtered = events
        if workflow_id or task_id:
            filtered = [
                e
                for e in events
                if (
                    not workflow_id
                    or getattr(e, "payload", {}).get("workflow_id") == workflow_id
                    or getattr(e, "payload", {}).get("root_task_id") == workflow_id
                )
                and (not task_id or getattr(e, "payload", {}).get("task_id") == task_id)
            ]
        return {"graph": WorkflowGraphBuilder().build(filtered)}
