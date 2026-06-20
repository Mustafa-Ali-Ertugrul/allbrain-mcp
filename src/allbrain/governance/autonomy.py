from __future__ import annotations

from typing import Any

from allbrain.governance.utils import autonomy_level


class AutonomyBoundaryController:
    def assess(self, context: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
        current = autonomy_level(context.get("current_autonomy_level"), 2)
        requested = max([current, *[autonomy_level(proposal.get("requested_autonomy_level"), current) for proposal in proposals]])
        allowed = min(5, current + 1)
        impact = max(0, requested - current)
        constraints: list[str] = []
        if impact > 1:
            constraints.append("limit_autonomy_transition_to_single_band")
        if requested >= 4:
            constraints.append("require_supervised_architecture_mutation")
        return {
            "current_autonomy_level": current,
            "requested_autonomy_level": requested,
            "autonomy_level_allowed": min(requested, allowed),
            "autonomy_impact": impact,
            "requires_escalation": impact > 2 or requested == 5,
            "constraints": constraints,
        }

    def next_allowed_level_from_events(self, successes: int, current_level: int) -> int:
        if successes >= 3:
            return min(5, current_level + 1)
        return current_level
