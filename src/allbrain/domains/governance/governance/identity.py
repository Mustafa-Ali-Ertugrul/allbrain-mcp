from __future__ import annotations

from typing import Any

from allbrain.domains.governance.governance.utils import clamp, unique


class IdentityConsistencyChecker:
    def check(self, context: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
        score = clamp(context.get("identity_consistency"), 0.85)
        flags: list[str] = []
        for proposal in proposals:
            if proposal.get("changes_core_identity"):
                score = min(score, 0.35)
                flags.append("core_identity_change")
            if proposal.get("mutation_type") == "interface_contract_change":
                score = min(score, 0.62)
                flags.append("interface_contract_pressure")
            if proposal.get("removes_auditability"):
                score = min(score, 0.45)
                flags.append("auditability_loss")
        return {"identity_consistency_score": score, "identity_flags": unique(flags)}
