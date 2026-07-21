from __future__ import annotations

from typing import Any


class ClosedLoopLearningEngine:
    def evaluate(self, prediction: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
        predicted_success = float(prediction.get("predicted_success", 0.75) or 0.75)
        actual_success = 1.0 if outcome.get("status") in {"planned", "completed", "success"} else 0.0
        error_delta = round(abs(predicted_success - actual_success), 6)
        proposal = None
        if error_delta >= 0.3:
            proposal = {
                "proposal_id": f"model_update:{outcome.get('run_id', 'unknown')}",
                "target": "execution_prediction",
                "reason": "prediction_outcome_gap",
                "error_delta": error_delta,
            }
        return {
            "prediction": dict(prediction),
            "outcome": dict(outcome),
            "error_delta": error_delta,
            "model_update_proposal": proposal,
        }
