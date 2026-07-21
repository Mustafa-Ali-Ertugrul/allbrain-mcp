from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TeamMember:
    agent_id: str
    role: str
    capabilities: set[str] = field(default_factory=set)
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "capabilities": sorted(self.capabilities),
            "weight": self.weight,
        }


@dataclass(frozen=True)
class AgentTeam:
    name: str
    purpose: str
    members: tuple[TeamMember, ...]
    supervisor: str | None = None

    @property
    def capabilities(self) -> set[str]:
        skills: set[str] = set()
        for member in self.members:
            skills.update(member.capabilities)
        return skills

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "members": [member.to_dict() for member in self.members],
            "capabilities": sorted(self.capabilities),
            "supervisor": self.supervisor,
        }
