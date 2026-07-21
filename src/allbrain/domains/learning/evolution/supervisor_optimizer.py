from __future__ import annotations

from collections import defaultdict
from typing import Any

from allbrain.models.schemas import EventRead


class SupervisorOptimizer:
    def optimize(self, events: list[EventRead]) -> list[dict[str, Any]]:
        interventions: dict[str, int] = defaultdict(int)
        completions: dict[str, int] = defaultdict(int)
        evidence: dict[str, list[str]] = defaultdict(list)
        for event in events:
            supervisor = event.payload.get("supervisor_id") or event.agent_id
            if not isinstance(supervisor, str):
                continue
            if event.type == "supervisor_intervention":
                interventions[supervisor] += 1
                evidence[supervisor].append(event.id)
            elif event.type == "collaboration_completed":
                completions[supervisor] += 1
                evidence[supervisor].append(event.id)
        supervisors = sorted(set(interventions) | set(completions))
        return [
            {
                "supervisor_id": supervisor,
                "intervention_count": interventions[supervisor],
                "completed_collaborations": completions[supervisor],
                "effectiveness_score": round(completions[supervisor] / max(interventions[supervisor], 1), 6),
                "evidence_event_ids": evidence[supervisor],
            }
            for supervisor in supervisors
        ]
