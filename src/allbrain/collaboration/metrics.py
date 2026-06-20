from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from allbrain.models.schemas import EventRead


class CollaborationMetrics:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        counts = Counter(event.type for event in events)
        delegation_successes = counts["delegation_completed"]
        delegation_total = counts["delegation_completed"] + counts["delegation_failed"]
        negotiation_successes = counts["negotiation_completed"]
        negotiation_total = counts["negotiation_completed"] + counts["negotiation_timeout"]
        votes_by_agent: dict[str, int] = defaultdict(int)
        for event in events:
            if event.type == "vote_cast" and isinstance(event.payload.get("agent_id"), str):
                votes_by_agent[event.payload["agent_id"]] += 1
        return {
            "delegation_count": counts["delegation_created"],
            "delegation_success_rate": round(delegation_successes / delegation_total, 6) if delegation_total else 0.0,
            "negotiation_count": counts["negotiation_started"],
            "negotiation_success_rate": round(negotiation_successes / negotiation_total, 6) if negotiation_total else 0.0,
            "consensus_participation": dict(sorted(votes_by_agent.items())),
            "team_efficiency": _team_efficiency(events),
            "supervisor_effectiveness": _supervisor_effectiveness(events),
        }


def _team_efficiency(events: list[EventRead]) -> dict[str, float]:
    totals: dict[str, int] = defaultdict(int)
    successes: dict[str, int] = defaultdict(int)
    for event in events:
        team = event.payload.get("team_name")
        if not isinstance(team, str):
            continue
        if event.type in {"collaboration_completed", "collaboration_failed"}:
            totals[team] += 1
            if event.type == "collaboration_completed":
                successes[team] += 1
    return {team: round(successes[team] / totals[team], 6) for team in sorted(totals)}


def _supervisor_effectiveness(events: list[EventRead]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.type == "supervisor_intervention" and isinstance(event.payload.get("supervisor_id"), str):
            counts[event.payload["supervisor_id"]] += 1
    return dict(sorted(counts.items()))
