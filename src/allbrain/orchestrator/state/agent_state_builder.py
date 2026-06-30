from __future__ import annotations

from typing import Any

from allbrain.orchestrator.agent_profile import AgentProfile
from allbrain.orchestrator.capabilities import CapabilityRegistry


class AgentStateBuilder:
    def __init__(self, registry: CapabilityRegistry | None = None):
        self.registry = registry or CapabilityRegistry.from_env()

    def build(self, *, metrics: dict[str, dict[str, Any]], task_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        agents = set(self.registry.agents()) | set(metrics)
        queues = task_state.get("agent_queue", {})
        return {
            agent_id: {
                "agent_id": agent_id,
                "version": self._profile(agent_id).version,
                "capabilities": self._profile(agent_id).capabilities_by_domain(),
                "health": self._health(agent_id, metrics.get(agent_id, self._empty_metrics(agent_id))),
                "cost": self._profile(agent_id).cost,
                "performance": {
                    "metric_key": f"{agent_id}@{self._profile(agent_id).version}",
                    "success_rate": metrics.get(agent_id, self._empty_metrics(agent_id))["success_rate"],
                    "total_tasks": metrics.get(agent_id, self._empty_metrics(agent_id))["total_tasks"],
                    "user_feedback_score": metrics.get(agent_id, self._empty_metrics(agent_id)).get(
                        "user_feedback_score"
                    ),
                },
                "metrics": metrics.get(agent_id, self._empty_metrics(agent_id)),
                "current_load": len(queues.get(agent_id, [])),
            }
            for agent_id in sorted(agents)
        }

    def _profile(self, agent_id: str) -> AgentProfile:
        return AgentProfile.from_raw(agent_id, self.registry.capabilities.get(agent_id, {}))

    def _health(self, agent_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        return AgentProfile.from_raw(
            agent_id,
            self.registry.capabilities.get(agent_id, {}),
            metrics=metrics,
        ).health.to_dict()

    def _empty_metrics(self, agent_id: str) -> dict[str, Any]:
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
