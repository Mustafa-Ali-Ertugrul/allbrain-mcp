from __future__ import annotations

from typing import Any

from uuid6 import uuid7


class SelfModificationAuthorityEngine:
    REJECT_ALIGNMENT = 0.45
    REJECT_TRAJECTORY = 0.35
    REJECT_SAFETY = 0.40
    RESTRUCTURE_IDENTITY = 0.50
    DELAY_CONFIDENCE = 0.50
    APPROVE_SCORE = 0.75
    APPROVE_CONFIDENCE = 0.70

    def decide(
        self,
        *,
        proposals: list[dict[str, Any]],
        alignment_report: dict[str, Any],
        trajectory: dict[str, Any],
        identity: dict[str, Any],
        autonomy_assessment: dict[str, Any],
        constitutional: dict[str, Any],
    ) -> dict[str, Any]:
        risk_level = _risk_level(proposals)
        confidence = min(float(trajectory["confidence"]), _proposal_confidence(proposals))
        has_architecture_mutation = any(proposal.get("change_type") == "architecture_change" for proposal in proposals)
        weakens_auditability = any(proposal.get("removes_auditability") or proposal.get("reduces_interpretability") for proposal in proposals)

        if (
            constitutional["has_explicit_violation"]
            or alignment_report["alignment_score"] < self.REJECT_ALIGNMENT
            or trajectory["trajectory_score"] < self.REJECT_TRAJECTORY
            or alignment_report["safety_alignment_score"] < self.REJECT_SAFETY
        ):
            decision = "reject_expansion"
            reason = "alignment_or_constitutional_boundary_failed"
        elif identity["identity_consistency_score"] < self.RESTRUCTURE_IDENTITY or (has_architecture_mutation and weakens_auditability):
            decision = "require_restructuring"
            reason = "identity_or_auditability_requires_restructure"
        elif confidence < self.DELAY_CONFIDENCE or trajectory["confidence"] < self.DELAY_CONFIDENCE:
            decision = "delay_expansion"
            reason = "insufficient_governance_confidence"
        elif autonomy_assessment["requires_escalation"]:
            decision = "escalate_to_supervision"
            reason = "autonomy_transition_exceeds_governance_band"
        elif (
            risk_level == "high"
            or autonomy_assessment["autonomy_impact"] > 1
            or trajectory["trajectory_score"] < self.APPROVE_SCORE
            or alignment_report["alignment_score"] < self.APPROVE_SCORE
            or any(proposal.get("reduces_interpretability") for proposal in proposals)
        ):
            decision = "approve_with_constraints"
            reason = "constrain_first_governance"
        else:
            decision = "approve_expansion"
            reason = "alignment_and_trajectory_within_governance_bounds"

        return {
            "decision_id": str(uuid7()),
            "proposal_id": _first_proposal_id(proposals),
            "decision": decision,
            "risk_level": risk_level,
            "confidence": round(confidence, 6),
            "reasoning": reason,
            "rollback_conditions": [
                "alignment_score_degrades",
                "trajectory_score_degrades",
                "constitutional_violation_detected",
            ],
        }


def _risk_level(proposals: list[dict[str, Any]]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    selected = "low"
    for proposal in proposals:
        risk = str(proposal.get("risk_level", "low"))
        if order.get(risk, 0) > order[selected]:
            selected = "high" if risk == "critical" else risk
    return selected


def _proposal_confidence(proposals: list[dict[str, Any]]) -> float:
    values = [float(proposal.get("confidence", 0.75)) for proposal in proposals]
    return min(values) if values else 0.75


def _first_proposal_id(proposals: list[dict[str, Any]]) -> str | None:
    for proposal in proposals:
        if isinstance(proposal.get("proposal_id"), str):
            return proposal["proposal_id"]
    return None
