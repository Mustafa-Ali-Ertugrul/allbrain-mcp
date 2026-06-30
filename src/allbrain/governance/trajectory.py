from __future__ import annotations

from typing import Any

from uuid6 import uuid7

from allbrain.governance.utils import clamp


class SystemTrajectoryForecaster:
    def forecast(self, context: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
        alignment_decay = clamp(context.get("alignment_decay_risk"), 0.1)
        risk_growth = clamp(context.get("risk_growth"), 0.1)
        autonomy_growth = clamp(context.get("autonomy_growth"), 0.1)
        confidence = clamp(context.get("trajectory_confidence"), 0.75)
        predicted_capabilities: list[str] = []

        for proposal in proposals:
            if proposal.get("alignment_decay_risk") is not None:
                alignment_decay = max(alignment_decay, clamp(proposal.get("alignment_decay_risk")))
            if proposal.get("risk_growth") is not None:
                risk_growth = max(risk_growth, clamp(proposal.get("risk_growth")))
            if proposal.get("requested_autonomy_level") is not None:
                autonomy_growth = max(autonomy_growth, 0.2)
            if isinstance(proposal.get("capability"), str):
                predicted_capabilities.append(proposal["capability"])

        trajectory_score = round((1.0 - alignment_decay + 1.0 - risk_growth + confidence) / 3, 6)
        return {
            "trajectory_id": str(uuid7()),
            "projection_horizon": context.get("projection_horizon", "long"),
            "predicted_capabilities": sorted(set(predicted_capabilities)),
            "risk_evolution_curve": [round(risk_growth * factor, 6) for factor in (0.5, 0.75, 1.0)],
            "autonomy_growth_curve": [round(autonomy_growth * factor, 6) for factor in (0.5, 0.75, 1.0)],
            "alignment_decay_risk": alignment_decay,
            "governance_pressure_index": round(max(alignment_decay, risk_growth, autonomy_growth), 6),
            "scenario_type": "high_pressure"
            if max(alignment_decay, risk_growth, autonomy_growth) >= 0.75
            else "baseline",
            "trajectory_score": trajectory_score,
            "confidence": confidence,
        }
