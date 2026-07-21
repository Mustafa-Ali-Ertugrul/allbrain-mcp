from __future__ import annotations

from collections import defaultdict

from allbrain.domains.learning.evolution.team_pattern import TeamPattern
from allbrain.models.schemas import EventRead


class TeamOptimizer:
    def optimize(self, events: list[EventRead]) -> list[TeamPattern]:
        totals: dict[str, list[EventRead]] = defaultdict(list)
        successes: dict[str, int] = defaultdict(int)
        members: dict[str, set[str]] = defaultdict(set)
        for event in events:
            team = event.payload.get("team_name")
            if not isinstance(team, str):
                continue
            agent = (
                event.agent_id
                or event.payload.get("agent_id")
                or event.payload.get("from_agent")
                or event.payload.get("to_agent")
            )
            if isinstance(agent, str):
                members[team].add(agent)
            if event.type in {"collaboration_completed", "collaboration_failed"}:
                totals[team].append(event)
                if event.type == "collaboration_completed":
                    successes[team] += 1
        patterns: list[TeamPattern] = []
        for team, team_events in sorted(totals.items()):
            sample_size = len(team_events)
            patterns.append(
                TeamPattern(
                    team_name=team,
                    members=tuple(sorted(members[team])),
                    success_rate=round(successes[team] / sample_size, 6) if sample_size else 0.0,
                    sample_size=sample_size,
                    evidence_event_ids=tuple(event.id for event in team_events),
                )
            )
        return patterns
