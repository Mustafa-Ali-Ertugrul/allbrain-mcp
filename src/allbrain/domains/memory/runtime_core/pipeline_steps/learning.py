from __future__ import annotations

from typing import Any

from allbrain.domains.memory.runtime_core.pipeline_models import PipelineRunState
from allbrain.domains.memory.runtime_core.pipeline_services import PipelineServices
from allbrain.domains.memory.runtime_core.state import RuntimeStatus
from allbrain.events import EventType


class LearningCompletionStep:
    """Evaluate feedback, emit learning signals, and complete the run."""

    def execute(self, state: PipelineRunState, services: PipelineServices) -> bool:
        state.transition(RuntimeStatus.EVOLUTION, "closed_loop_learning")
        prediction = self._learning_prediction(state)
        state.learning = services.learning.evaluate(prediction, state.feedback or {})
        if state.learning["error_delta"] >= 0.3:
            state.publish(EventType.PREDICTION_ERROR_DETECTED.value, state.learning, caused_by=state.last_event_id)
        if state.learning["model_update_proposal"]:
            state.publish(
                EventType.MODEL_UPDATE_PROPOSED.value,
                state.learning["model_update_proposal"],
                caused_by=state.last_event_id,
            )
        state.transition(RuntimeStatus.COMPLETED, "pipeline_completed")
        state.publish(
            EventType.PIPELINE_RUN_COMPLETED.value,
            self._completed_payload(state),
            caused_by=state.last_event_id,
        )
        state.status = "COMPLETED"
        return True

    @staticmethod
    def _learning_prediction(state: PipelineRunState) -> dict[str, Any]:
        prediction = dict(state.execution_plan)
        if state.counterfactual is not None and state.counterfactual.get("best") is not None:
            best = state.counterfactual["best"]
            prediction["best_alternative"] = best["alternative_prediction"]["success_probability"]
            prediction["regret"] = best["regret"]
        if state.scenarios is not None:
            prediction["prediction_spread"] = state.scenarios["prediction_spread"]
            prediction["risk_volatility"] = state.scenarios["risk_volatility"]
            prediction["uncertainty"] = state.scenarios["uncertainty"]
        if state.foresight is not None:
            prediction["future_horizon"] = state.foresight["expected_plan"]["horizon"]
            prediction["strategy_uncertainty"] = state.foresight["strategy_uncertainty"]
            prediction["horizon_risk"] = state.foresight["horizon_risk"]
        return prediction

    @staticmethod
    def _completed_payload(state: PipelineRunState) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": "COMPLETED", "final_decision": state.final_decision}
        optional = {
            "world_simulation": state.world_simulation,
            "counterfactual": state.counterfactual,
            "scenarios": state.scenarios,
            "foresight": state.foresight,
            "meta_reasoning": state.meta_reasoning,
            "uncertainty": state.uncertainty,
            "information_seeking": state.information_seeking,
            "learning": state.learning,
        }
        payload.update({key: value for key, value in optional.items() if value is not None})
        return payload
