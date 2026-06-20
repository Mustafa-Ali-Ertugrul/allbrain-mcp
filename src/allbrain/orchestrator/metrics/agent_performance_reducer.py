from __future__ import annotations

from math import log
from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class AgentPerformanceReducer:
    def reduce(self, events: list[EventRead]) -> dict[str, dict[str, Any]]:
        metrics: dict[str, dict[str, Any]] = {}
        for event in events:
            agent_id = self._agent_for_event(event)
            if agent_id is None:
                continue
            agent = metrics.setdefault(agent_id, self._empty(agent_id))
            if event.type == EventType.TASK_ASSIGNED.value:
                agent["assigned_count"] += 1
            elif event.type == EventType.TASK_COMPLETED.value:
                agent["success_count"] += 1
                agent["consecutive_failures"] = 0
            elif event.type == EventType.TASK_FAILED.value:
                agent["failure_count"] += 1
                agent["consecutive_failures"] += 1
                agent["last_failure_at"] = event.created_at.isoformat()
                reason = event.payload.get("reason") or event.payload.get("error_type") or event.payload.get("error")
                if isinstance(reason, str) and reason:
                    agent["last_failure_reason"] = reason
            elif event.type == EventType.TASK_BLOCKED.value:
                agent["blocked_count"] += 1
            elif event.type == "user_feedback":
                score = event.payload.get("score")
                if isinstance(score, int | float):
                    agent["user_feedback_score"] = score
            version = event.payload.get("agent_version")
            if isinstance(version, str) and version:
                agent["agent_version"] = version

        for agent in metrics.values():
            total_tasks = agent["success_count"] + agent["failure_count"] + agent["blocked_count"]
            agent["total_tasks"] = total_tasks
            denominator = max(1, total_tasks)
            agent["success_rate"] = agent["success_count"] / denominator
            agent["failure_rate"] = agent["failure_count"] / denominator
            agent["blocked_rate"] = agent["blocked_count"] / denominator
            agent["confidence"] = min(1.0, log(total_tasks + 1) / log(50))
        return dict(sorted(metrics.items()))

    def _agent_for_event(self, event: EventRead) -> str | None:
        if event.type == EventType.TASK_ASSIGNED.value:
            agent_id = event.payload.get("agent_id")
            return agent_id if isinstance(agent_id, str) and agent_id else event.agent_id
        return event.agent_id

    def _empty(self, agent_id: str) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "agent_version": None,
            "success_count": 0,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 0,
            "total_tasks": 0,
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "blocked_rate": 0.0,
            "confidence": 0.0,
            "user_feedback_score": None,
            "consecutive_failures": 0,
            "last_failure_at": None,
            "last_failure_reason": None,
        }
