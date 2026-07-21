from __future__ import annotations

from allbrain.domains.memory.runtime_core.contracts import EconomicEvaluation, ObjectiveContext


class EconomicEvaluationBridge:
    engine_id = "deterministic-economic-v1"

    def evaluate(self, objective: ObjectiveContext) -> EconomicEvaluation:
        expected_value = objective.expected_value
        if expected_value is None:
            expected_value = max(1, objective.priority) * 10.0
        estimated_cost = objective.estimated_cost
        risk_level = objective.risk_level
        risk_penalty = {"low": 0.05, "medium": 0.15, "high": 0.35, "critical": 0.65}.get(risk_level, 0.15)
        roi = expected_value / max(estimated_cost, 1.0)
        risk_adjusted_value = round(expected_value * (1.0 - risk_penalty) - estimated_cost, 6)
        if risk_adjusted_value < 0:
            decision = "delay"
        elif roi < 1.0:
            decision = "request_research"
        else:
            decision = "invest"
        return EconomicEvaluation(
            expected_value=expected_value,
            estimated_cost=estimated_cost,
            roi=round(roi, 6),
            risk_adjusted_value=risk_adjusted_value,
            risk_level=risk_level,
            decision=decision,
            confidence=objective.economic_confidence or objective.confidence,
            engine_id=self.engine_id,
        )
