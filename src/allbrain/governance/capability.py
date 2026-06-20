from __future__ import annotations

from typing import Any


class CapabilityExpansionGatekeeper:
    def evaluate(self, proposals: list[dict[str, Any]], autonomy_assessment: dict[str, Any]) -> dict[str, Any]:
        blocked: list[str] = []
        gated: list[str] = []
        for proposal in proposals:
            capability = proposal.get("capability")
            if not isinstance(capability, str):
                continue
            if proposal.get("risk_level") == "critical" or autonomy_assessment["requires_escalation"]:
                blocked.append(capability)
            elif proposal.get("risk_level") in {"high", "medium"}:
                gated.append(capability)
        return {"blocked_capabilities": blocked, "gated_capabilities": gated}
