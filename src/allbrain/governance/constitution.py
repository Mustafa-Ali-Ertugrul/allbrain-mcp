from __future__ import annotations

from typing import Any

from allbrain.governance.utils import unique


class ConstitutionalReasoner:
    PRINCIPLES = [
        "do_not_trade_long_term_alignment_for_short_term_gain",
        "do_not_expand_autonomy_without_safety_validation",
        "preserve_interpretability",
        "maintain_auditability",
    ]

    def reason(self, context: dict[str, Any], proposals: list[dict[str, Any]], alignment_report: dict[str, Any]) -> dict[str, Any]:
        violations: list[str] = list(context.get("constitutional_violations", []))
        for proposal in proposals:
            if proposal.get("short_term_gain_bias") and alignment_report["long_term_drift_score"] > 0.4:
                violations.append("do_not_trade_long_term_alignment_for_short_term_gain")
            if proposal.get("requested_autonomy_level") and not proposal.get("safety_validation"):
                violations.append("do_not_expand_autonomy_without_safety_validation")
            if proposal.get("removes_auditability"):
                violations.append("maintain_auditability")
        return {
            "principles": list(self.PRINCIPLES),
            "violations": unique([str(violation) for violation in violations]),
            "has_explicit_violation": bool(violations),
        }
