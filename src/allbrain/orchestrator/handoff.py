from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.orchestrator.scheduler import DeterministicScheduler


class HandoffEngine:
    def __init__(self, scheduler: DeterministicScheduler | None = None):
        self.scheduler = scheduler or DeterministicScheduler()

    def recommend(
        self,
        *,
        task: dict[str, Any],
        task_state: dict[str, Any],
        from_agent: str,
        to_agent: str | None = None,
        events: list[EventRead] | None = None,
        metrics: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        assignment = self.scheduler.choose_agent(
            task=task,
            task_state=task_state,
            explicit_agent_id=to_agent,
            exclude_agent_id=from_agent if to_agent is None else None,
            events=events,
            metrics=metrics,
        )
        return {
            "from_agent": from_agent,
            "to_agent": assignment["agent_id"],
            "assignment": assignment,
        }
