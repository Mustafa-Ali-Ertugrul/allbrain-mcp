from __future__ import annotations

from typing import Any


class ExecutionPlanningBridge:
    def plan(self, objective: dict[str, Any], economic: dict[str, Any], decomposition: dict[str, Any]) -> dict[str, Any]:
        confidence = float(objective.get("confidence", economic.get("confidence", 0.75)) or 0.75)
        if economic["risk_level"] in {"high", "critical"}:
            strategy = "safe_execution"
        elif confidence < 0.55:
            strategy = "research_first_execution"
        else:
            strategy = "adaptive_hybrid_execution"
        return {
            "execution_plan_id": f"execution:{decomposition['task_id']}",
            "strategy": strategy,
            "max_parallel": 1 if strategy != "adaptive_hybrid_execution" else 3,
            "predicted_success": round(max(0.05, min(confidence * (1.0 if economic["risk_level"] == "low" else 0.85), 0.99)), 6),
            "predicted_cost": economic["estimated_cost"],
        }
