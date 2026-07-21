from __future__ import annotations

from typing import Any


class ArbitrationBridge:
    def arbitrate(
        self, governance: dict[str, Any], economic: dict[str, Any], execution_plan: dict[str, Any]
    ) -> dict[str, Any]:
        conflicts: list[str] = []
        governance_decision = governance["governance_decision"]["decision"]
        if governance_decision in {"reject_expansion", "require_restructuring", "escalate_to_supervision"}:
            conflicts.append("governance_blocks_execution")
        if (
            economic["decision"] in {"delay", "request_research"}
            and execution_plan["strategy"] != "research_first_execution"
        ):
            conflicts.append("economic_uncertainty_vs_execution")
        if (
            governance_decision == "approve_with_constraints"
            and execution_plan["strategy"] == "adaptive_hybrid_execution"
        ):
            conflicts.append("governance_constraints_vs_execution_speed")

        if "governance_blocks_execution" in conflicts:
            action = "reject"
        elif conflicts:
            action = "modify"
        else:
            action = "accept"
        return {"action": action, "conflicts": conflicts, "confidence": 0.8 if not conflicts else 0.62}
