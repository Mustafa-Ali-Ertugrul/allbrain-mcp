from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from allbrain.collaboration.team import AgentTeam


@dataclass
class TeamRegistry:
    teams: dict[str, AgentTeam] = field(default_factory=dict)

    def register(self, team: AgentTeam) -> AgentTeam:
        self.teams[team.name] = team
        return team

    def get(self, name: str) -> AgentTeam | None:
        return self.teams.get(name)

    def find_by_capability(self, capability: str) -> list[dict[str, Any]]:
        return [team.to_dict() for team in sorted(self.teams.values(), key=lambda item: item.name) if capability in team.capabilities]

    def to_dict(self) -> dict[str, Any]:
        return {name: team.to_dict() for name, team in sorted(self.teams.items())}
