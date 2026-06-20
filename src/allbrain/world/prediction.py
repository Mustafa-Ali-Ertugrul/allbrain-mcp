from __future__ import annotations

from allbrain.world.models import Prediction, WorldState


class PredictionBridge:
    def evaluate(self, state: WorldState, action: str) -> Prediction:
        if action == "deploy":
            if not state.environment_state.get("tests"):
                return Prediction(
                    success_probability=0.35,
                    risk=0.8,
                    cost=0.4,
                    confidence=0.9,
                    explanation="Tests missing.",
                )
            return Prediction(
                success_probability=0.9,
                risk=0.1,
                cost=0.2,
                confidence=0.95,
                explanation="Tests passed; low risk.",
            )
        if action == "run_tests":
            return Prediction(
                success_probability=0.95,
                risk=0.05,
                cost=0.15,
                confidence=0.95,
                explanation="Test execution has well-understood cost.",
            )
        return Prediction(
            success_probability=0.85,
            risk=0.15,
            cost=0.25,
            confidence=0.7,
            explanation="Default moderate confidence for unknown action.",
        )
