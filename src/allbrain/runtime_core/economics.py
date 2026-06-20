from __future__ import annotations

from typing import Any


class EconomicEvaluationBridge:
    def evaluate(self, objective: dict[str, Any]) -> dict[str, Any]:
        expected_value = float(objective.get("expected_value", max(1, int(objective.get("priority", 3))) * 10.0) or 0.0)
        estimated_cost = float(objective.get("estimated_cost", 10.0) or 0.0)
        risk_level = str(objective.get("risk_level", "medium"))
        risk_penalty = {"low": 0.05, "medium": 0.15, "high": 0.35, "critical": 0.65}.get(risk_level, 0.15)
        roi = expected_value / max(estimated_cost, 1.0)
        risk_adjusted_value = round(expected_value * (1.0 - risk_penalty) - estimated_cost, 6)
        if risk_adjusted_value < 0:
            decision = "delay"
        elif roi < 1.0:
            decision = "request_research"
        else:
            decision = "invest"
        return {
            "expected_value": expected_value,
            "estimated_cost": estimated_cost,
            "roi": round(roi, 6),
            "risk_adjusted_value": risk_adjusted_value,
            "risk_level": risk_level,
            "decision": decision,
            "confidence": float(objective.get("economic_confidence", objective.get("confidence", 0.75)) or 0.75),
        }
