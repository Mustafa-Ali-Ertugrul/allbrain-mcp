from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.domains.memory.observability import ObservabilityBuilder


class FailureAnalyzer:
    def analyze(self, events: list[EventRead]) -> dict[str, Any]:
        decisions = ObservabilityBuilder().selection_decisions(events)
        by_task = {decision.get("task_id"): decision for decision in decisions}
        failures: list[dict[str, Any]] = []
        for event in events:
            if event.type not in {EventType.TASK_FAILED.value, EventType.AGENT_EXECUTION_FAILED.value}:
                continue
            task_id = event.payload.get("task_id")
            decision = by_task.get(task_id)
            failures.append(
                {
                    "event_id": event.id,
                    "task_id": task_id,
                    "node_id": event.payload.get("node_id"),
                    "agent_id": event.payload.get("agent_id") or event.agent_id,
                    "reason": event.payload.get("reason")
                    or event.payload.get("error")
                    or event.payload.get("error_type"),
                    "preceding_decision": decision,
                    "root_cause_event_id": event.caused_by or event.id,
                }
            )
        return {"failures": failures, "count": len(failures)}
