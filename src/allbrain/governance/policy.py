from __future__ import annotations

from typing import Any


class GovernancePolicySynthesizer:
    def synthesize(
        self,
        decision: str,
        alignment_report: dict[str, Any],
        trajectory: dict[str, Any],
        autonomy_assessment: dict[str, Any],
        constitutional: dict[str, Any],
    ) -> dict[str, Any]:
        constraints = list(autonomy_assessment.get("constraints", []))
        if decision in {"approve_with_constraints", "partial_approval", "delay_expansion"}:
            constraints.append("canary_rollout")
            constraints.append("post_change_alignment_check")
        if alignment_report["alignment_score"] < 0.75:
            constraints.append("alignment_monitoring_required")
        if trajectory["trajectory_score"] < 0.75:
            constraints.append("trajectory_review_required")
        if constitutional["violations"]:
            constraints.append("constitutional_override_block")
        return {
            "constraints": list(dict.fromkeys(constraints)),
            "policy_updates": [
                {
                    "policy_id": "autonomous_governance",
                    "suggested_change": "tighten_constraints" if decision != "approve_expansion" else "maintain_current_thresholds",
                    "reason": decision,
                }
            ],
        }
