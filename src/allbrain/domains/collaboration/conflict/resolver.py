from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead


class ConflictResolver:
    def __init__(self, decision_margin: float = 0.25):
        self.decision_margin = decision_margin

    def resolve(
        self, conflicts: list[dict[str, Any]], events: list[EventRead], agent_view: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        events_by_id = {event.id: event for event in events}
        confidence_by_agent = {agent["agent_id"]: agent["confidence_score"] for agent in agent_view}
        resolved = []
        for conflict in conflicts:
            evidence = [
                events_by_id[event_id] for event_id in conflict["evidence_event_ids"] if event_id in events_by_id
            ]
            if not evidence:
                continue
            ranked = sorted(
                evidence,
                key=lambda event: (
                    confidence_by_agent.get(event.agent_id or "unknown", 0.0),
                    event.impact_score or 0.0,
                    event.id,
                ),
                reverse=True,
            )
            winner = ranked[0]
            runner_up = ranked[1] if len(ranked) > 1 else None
            winner_confidence = confidence_by_agent.get(winner.agent_id or "unknown", 0.0)
            runner_up_confidence = confidence_by_agent.get(runner_up.agent_id or "unknown", 0.0) if runner_up else 0.0
            margin = winner_confidence - runner_up_confidence
            status = "resolved" if margin >= self.decision_margin else "needs_review"
            resolved.append(
                {
                    "conflict": conflict,
                    "status": status,
                    "winner_event_id": winner.id if status == "resolved" else None,
                    "winner_agent_id": (winner.agent_id or "unknown") if status == "resolved" else None,
                    "candidate_event_id": winner.id,
                    "candidate_agent_id": winner.agent_id or "unknown",
                    "confidence_margin": round(margin, 4),
                    "strategy": "dynamic_confidence_then_impact_then_uuidv7",
                }
            )
        return resolved
