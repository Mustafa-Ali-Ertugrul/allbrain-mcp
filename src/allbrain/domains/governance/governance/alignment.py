from __future__ import annotations

from typing import Any

from uuid6 import uuid7

from allbrain.domains.governance.governance.utils import clamp, unique


class AlignmentEvaluator:
    def evaluate(self, context: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
        objective_alignment = clamp(context.get("objective_alignment"), 0.85)
        value_alignment = clamp(context.get("value_alignment"), 0.85)
        policy_alignment = clamp(context.get("policy_alignment"), 0.85)
        safety_alignment = clamp(context.get("safety_alignment"), 0.85)
        behavioral_drift = clamp(context.get("behavioral_drift_score"), 0.1)
        long_term_drift = clamp(context.get("long_term_drift_score"), 0.1)
        evidence_refs: list[str] = list(context.get("evidence_refs", []))
        flags: list[str] = []

        for proposal in proposals:
            evidence_refs.extend(str(ref) for ref in proposal.get("evidence_refs", []))
            if proposal.get("reduces_interpretability"):
                policy_alignment = min(policy_alignment, 0.68)
                flags.append("interpretability_reduction")
            if proposal.get("alignment_decay_risk") is not None:
                risk = clamp(proposal.get("alignment_decay_risk"))
                long_term_drift = max(long_term_drift, risk)
                safety_alignment = min(safety_alignment, 1.0 - risk)
            if proposal.get("policy_dependency_erosion"):
                policy_alignment = min(policy_alignment, 0.55)
                flags.append("policy_dependency_erosion")
            if proposal.get("short_term_gain_bias"):
                value_alignment = min(value_alignment, 0.62)
                flags.append("short_term_gain_bias")

        alignment_score = round(
            (
                objective_alignment
                + value_alignment
                + policy_alignment
                + safety_alignment
                + (1.0 - behavioral_drift)
                + (1.0 - long_term_drift)
            )
            / 6,
            6,
        )
        return {
            "report_id": str(uuid7()),
            "objective_alignment": objective_alignment,
            "value_alignment": value_alignment,
            "policy_alignment": policy_alignment,
            "behavioral_drift_score": behavioral_drift,
            "long_term_drift_score": long_term_drift,
            "safety_alignment_score": safety_alignment,
            "alignment_score": alignment_score,
            "inconsistency_flags": unique(flags),
            "evidence_refs": unique(evidence_refs),
        }
