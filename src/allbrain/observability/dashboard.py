from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from allbrain.events import EventType
from allbrain.metrics import AdvancedMetrics, AgentRanking
from allbrain.models.schemas import EventRead
from allbrain.observability.dashboard_data_builder import DashboardDataBuilder
from allbrain.observability.exporter import SpanExporter
from allbrain.observability.tracer import Tracer
from allbrain.orchestrator.metrics import AgentPerformanceReducer


class ObservabilityBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        decisions = self.selection_decisions(events)
        spans = Tracer().build_spans(events)
        return {
            "selection_decisions": decisions,
            "workflow_replay": self.workflow_replay(events, decisions=decisions),
            "agent_comparison": self.agent_comparison(events, decisions=decisions),
            "trace": Tracer().trace_tree(events),
            "dashboard_metrics": DashboardDataBuilder().build(events),
            "advanced_metrics": AdvancedMetrics().build(events),
            "agent_ranking": AgentRanking().leaderboard(events),
            "exports": {
                "json": SpanExporter().to_json(spans),
                "otel": SpanExporter().to_otel(spans),
                "prometheus": SpanExporter().to_prometheus(spans),
            },
        }

    def selection_decisions(self, events: list[EventRead]) -> list[dict[str, Any]]:
        decisions: list[dict[str, Any]] = []
        for event in events:
            if event.type == EventType.SELECTION_DECISION.value:
                decisions.append(self._decision_from_selection_event(event))
            elif event.type == EventType.TASK_ASSIGNED.value and "breakdown" in event.payload:
                decisions.append(self._decision_from_assignment_event(event))
        return decisions

    def workflow_replay(
        self,
        events: list[EventRead],
        *,
        decisions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        decision_by_event = {
            decision.get("assignment_event_id"): decision
            for decision in decisions or self.selection_decisions(events)
            if decision.get("assignment_event_id")
        }
        timelines: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            task_id = event.payload.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                continue
            item = {
                "event_id": event.id,
                "type": event.type,
                "created_at": event.created_at.isoformat(),
                "agent_id": event.agent_id or event.payload.get("agent_id"),
                "summary": self._summary(event),
            }
            if event.id in decision_by_event:
                item["selection_decision"] = decision_by_event[event.id]
            timelines[task_id].append(item)
        return {
            "tasks": {
                task_id: {"task_id": task_id, "timeline": timeline}
                for task_id, timeline in sorted(timelines.items())
            },
            "task_count": len(timelines),
        }

    def agent_comparison(
        self,
        events: list[EventRead],
        *,
        decisions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        metrics = AgentPerformanceReducer().reduce(events)
        decision_counts = Counter(
            decision["agent_id"]
            for decision in decisions or self.selection_decisions(events)
            if isinstance(decision.get("agent_id"), str)
        )
        agents = sorted(set(metrics) | set(decision_counts))
        return {
            agent_id: {
                "agent_id": agent_id,
                "selection_count": decision_counts[agent_id],
                "success_rate": metrics.get(agent_id, {}).get("success_rate", 0.0),
                "total_tasks": metrics.get(agent_id, {}).get("total_tasks", 0),
                "confidence": metrics.get(agent_id, {}).get("confidence", 0.0),
                "consecutive_failures": metrics.get(agent_id, {}).get("consecutive_failures", 0),
                "last_failure_reason": metrics.get(agent_id, {}).get("last_failure_reason"),
            }
            for agent_id in agents
        }

    def _decision_from_selection_event(self, event: EventRead) -> dict[str, Any]:
        payload = event.payload
        return {
            "event_id": event.id,
            "assignment_event_id": payload.get("assignment_event_id"),
            "task_id": payload.get("task_id"),
            "agent_id": payload.get("agent_id"),
            "total_score": payload.get("total_score", payload.get("score")),
            "breakdown": payload.get("breakdown", {}),
            "reason": payload.get("reason"),
            "fallback_mode": payload.get("fallback_mode", False),
            "created_at": event.created_at.isoformat(),
        }

    def _decision_from_assignment_event(self, event: EventRead) -> dict[str, Any]:
        payload = event.payload
        return {
            "event_id": event.id,
            "assignment_event_id": event.id,
            "task_id": payload.get("task_id"),
            "agent_id": payload.get("agent_id") or event.agent_id,
            "total_score": payload.get("score"),
            "breakdown": payload.get("breakdown", {}),
            "reason": payload.get("reason"),
            "fallback_mode": payload.get("fallback_mode", False),
            "created_at": event.created_at.isoformat(),
        }

    def _summary(self, event: EventRead) -> str:
        payload = event.payload
        if event.type == EventType.TASK_CREATED.value:
            return f"created: {payload.get('goal')}"
        if event.type == EventType.TASK_ASSIGNED.value:
            return f"assigned to {payload.get('agent_id') or event.agent_id}"
        if event.type == EventType.TASK_STARTED.value:
            return f"started by {event.agent_id}"
        if event.type == EventType.TASK_COMPLETED.value:
            return "completed"
        if event.type == EventType.TASK_FAILED.value:
            return f"failed: {payload.get('reason') or payload.get('error')}"
        if event.type == EventType.TASK_BLOCKED.value:
            return f"blocked: {payload.get('reason')}"
        if event.type == EventType.HANDOFF_CREATED.value:
            return f"handoff {payload.get('from_agent')} -> {payload.get('to_agent')}"
        return event.type
