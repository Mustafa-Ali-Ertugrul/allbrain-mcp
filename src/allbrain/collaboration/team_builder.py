from __future__ import annotations

from allbrain.collaboration.team import AgentTeam, TeamMember


class TeamBuilder:
    def build(self, *, name: str, purpose: str, members: list[dict[str, object]], supervisor: str | None = None) -> AgentTeam:
        return AgentTeam(
            name=name,
            purpose=purpose,
            supervisor=supervisor,
            members=tuple(
                TeamMember(
                    agent_id=str(member["agent_id"]),
                    role=str(member.get("role", "member")),
                    capabilities=set(str(skill) for skill in member.get("capabilities", [])),
                    weight=float(member.get("weight", 1.0) or 1.0),
                )
                for member in members
            ),
        )
