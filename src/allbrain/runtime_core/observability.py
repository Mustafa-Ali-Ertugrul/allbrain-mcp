"""Observability helpers extracted from SystemDecisionPipeline."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.runtime_core.contracts import RuntimeContext

logger = logging.getLogger(__name__)


class ObservabilityCollector:
    """Collects indicators and metrics from pipeline execution layers."""

    @staticmethod
    def collect_layer_indicators(
        world_simulation_payload: dict[str, Any] | None,
        counterfactual_payload: dict[str, Any] | None,
        scenario_payload: dict[str, Any] | None,
        foresight_payload: dict[str, Any] | None,
        meta_reasoning_payload: dict[str, Any] | None,
    ) -> list[float]:
        """Extract success probability indicators from each pipeline layer.

        Args:
            world_simulation_payload: World simulation results
            counterfactual_payload: Counterfactual analysis results
            scenario_payload: Scenario generation results
            foresight_payload: Foresight planning results
            meta_reasoning_payload: Meta-reasoning confidence results

        Returns:
            List of float indicators (success probabilities, confidence scores)
        """
        indicators: list[float] = []

        if world_simulation_payload is not None:
            sim = world_simulation_payload.get("prediction", {})
            if isinstance(sim, dict) and isinstance(sim.get("success_probability"), (int, float)):
                indicators.append(float(sim["success_probability"]))

        if counterfactual_payload is not None:
            best = counterfactual_payload.get("best")
            if isinstance(best, dict):
                pred = best.get("alternative_prediction") or best.get("actual_prediction")
                if isinstance(pred, dict) and isinstance(pred.get("success_probability"), (int, float)):
                    indicators.append(float(pred["success_probability"]))

        if scenario_payload is not None:
            best_case = scenario_payload.get("best_case", {})
            if isinstance(best_case, dict):
                pred = best_case.get("prediction", {})
                if isinstance(pred, dict) and isinstance(pred.get("success_probability"), (int, float)):
                    indicators.append(float(pred["success_probability"]))

        if foresight_payload is not None:
            best_plan = foresight_payload.get("best_plan", {})
            if isinstance(best_plan, dict) and isinstance(best_plan.get("predicted_success"), (int, float)):
                indicators.append(float(best_plan["predicted_success"]))

        if meta_reasoning_payload is not None:
            conf = meta_reasoning_payload.get("confidence", {})
            if isinstance(conf, dict) and isinstance(conf.get("confidence"), (int, float)):
                indicators.append(float(conf["confidence"]))

        return indicators

    @staticmethod
    def collect_historical_rate(
        context: RuntimeContext,
        project_path: str | None,
        *,
        objective: dict[str, Any] | None = None,
    ) -> float:
        """Compute historical success rate from past events.

        Args:
            context: Brain context with repository
            project_path: Project path to query events
            objective: Optional objective dict with 'kind' key for context filtering

        Returns:
            Historical success rate (0.0-1.0), defaults to 0.7 on error
        """
        from allbrain.domains.reasoning.uncertainty import observed_success_rate

        resolved = project_path or getattr(context, "project_path", None)
        if not resolved:
            return 0.7

        try:
            events = context.repository.list_events(project_path=resolved, limit=5000)
        except Exception as exc:
            logger.debug("Failed to collect historical event rate: %s", exc, exc_info=True)
            return 0.7

        context_key = None
        if isinstance(objective, dict):
            kind = objective.get("kind")
            if isinstance(kind, str) and kind:
                context_key = kind

        return observed_success_rate(events, context_key=context_key)

    @staticmethod
    def extract_objective_action(objective: dict[str, Any]) -> str:
        """Extract action string from objective dict.

        Args:
            objective: Objective dictionary

        Returns:
            Action string, defaults to 'execute'
        """
        return str(objective.get("kind", "execute"))

