from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.orchestrator.capabilities import CapabilityRegistry
from allbrain.orchestrator.metrics import AgentPerformanceReducer
from allbrain.orchestrator.scoring import SchedulerV1


class DeterministicScheduler:
    def __init__(self, registry: CapabilityRegistry | None = None):
        self.registry = registry or CapabilityRegistry.from_env()
        self.scheduler_v1 = SchedulerV1(self.registry)

    def choose_agent(
        self,
        *,
        task: dict[str, Any],
        task_state: dict[str, Any],
        explicit_agent_id: str | None = None,
        exclude_agent_id: str | None = None,
        events: list[EventRead] | None = None,
        metrics: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        metrics = metrics if metrics is not None else AgentPerformanceReducer().reduce(events or [])
        if explicit_agent_id:
            score = self.scheduler_v1.score_agent(
                agent_id=explicit_agent_id,
                task=task,
                metrics=metrics,
                task_state=task_state,
            )
            return {
                "agent_id": explicit_agent_id,
                "score": score["score"],
                "breakdown": score["breakdown"],
                "reason": "explicit_agent_override",
                "candidate_agents": [explicit_agent_id],
            }
        candidates = [agent for agent in self.registry.agents() if agent != exclude_agent_id]
        return self.scheduler_v1.assign_task(
            task=task,
            candidate_agents=candidates,
            metrics=metrics,
            task_state=task_state,
        )

    def _score(self, agent_id: str, task: dict[str, Any], task_state: dict[str, Any]) -> dict[str, Any]:
        capability = self.registry.score(agent_id, task.get("kind") or "implementation") * 6
        queue_size = len(task_state.get("agent_queue", {}).get(agent_id, []))
        availability = max(0, 20 - queue_size * 5)
        priority_bonus = int(task.get("priority") or 0) * 4
        breakdown = {
            "capability": capability,
            "availability": availability,
            "priority_bonus": priority_bonus,
        }
        return {"score": sum(breakdown.values()), "breakdown": breakdown}
