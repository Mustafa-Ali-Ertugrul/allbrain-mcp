from __future__ import annotations

from collections import defaultdict
from typing import Any

from allbrain.core import StateEngine
from allbrain.models.schemas import EventRead


class ParallelContextBuilder:
    def __init__(self, state_engine: StateEngine | None = None):
        self.state_engine = state_engine or StateEngine()

    def build_agent_view(self, events: list[EventRead]) -> list[dict[str, Any]]:
        events_by_agent: dict[str, list[EventRead]] = defaultdict(list)
        for event in events:
            events_by_agent[event.agent_id or "unknown"].append(event)

        agent_view = []
        for agent_id, agent_events in sorted(events_by_agent.items()):
            state = self.state_engine.build_state({"events": agent_events, "git": {}})
            completed_count = len(state["completed_tasks"])
            failure_count = len(state["failures"])
            blocker_count = len(state["blocked"])
            impact_score_total = sum(event.impact_score or 0.0 for event in agent_events)
            recency_bonus = 0.1 if agent_events else 0.0
            confidence = max(
                0.0,
                impact_score_total + completed_count - (0.5 * failure_count) - (0.5 * blocker_count) + recency_bonus,
            )
            agent_view.append(
                {
                    "agent_id": agent_id,
                    "current_task": state["open_tasks"][-1] if state["open_tasks"] else None,
                    "working_files": state["working_files"],
                    "completed": state["completed_tasks"],
                    "failures": state["failures"],
                    "event_count": len(agent_events),
                    "impact_score_total": round(impact_score_total, 4),
                    "confidence_score": round(confidence, 4),
                }
            )
        return agent_view
