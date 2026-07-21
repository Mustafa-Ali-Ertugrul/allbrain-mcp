from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from allbrain.events import EventType
from allbrain.domains.memory.runtime_core.contracts import EconomicEvaluator, RuntimeContext, StrategicPlanner
from allbrain.domains.memory.runtime_core.pipeline_models import PipelineRunOptions, PipelineRunState
from allbrain.domains.memory.runtime_core.pipeline_services import PipelineServices
from allbrain.domains.memory.runtime_core.pipeline_steps import (
    DecisionPreparationStep,
    ExecutionFeedbackStep,
    LearningCompletionStep,
    ReasoningStep,
)
from allbrain.domains.memory.runtime_core.state import RuntimeStatus


class SystemDecisionPipeline:
    """Backward-compatible facade for the live decision pipeline."""

    def __init__(
        self,
        *,
        economic_evaluator: EconomicEvaluator | None = None,
        strategic_planner: StrategicPlanner | None = None,
        bridge_timeout_ms: int = 500,
        services: PipelineServices | None = None,
        steps: Iterable[object] | None = None,
    ) -> None:
        self.services = services or PipelineServices.defaults(
            economic_evaluator=economic_evaluator,
            strategic_planner=strategic_planner,
            bridge_timeout_ms=bridge_timeout_ms,
        )
        if services is not None:
            if bridge_timeout_ms <= 0:
                raise ValueError("bridge_timeout_ms must be positive")
            self.services.bridge_timeout_ms = bridge_timeout_ms
            if economic_evaluator is not None:
                self.services.economics = economic_evaluator
            if strategic_planner is not None:
                self.services.strategy = strategic_planner
        self.steps = tuple(
            steps
            or (
                DecisionPreparationStep(),
                ReasoningStep(),
                ExecutionFeedbackStep(),
                LearningCompletionStep(),
            )
        )

    def run(
        self,
        context: RuntimeContext,
        objective: dict[str, Any],
        *,
        execute_mode: str = "event_only",
        project_path: str | None = None,
        limit: int = 5000,
        simulate_before_execute: bool = False,
        risk_threshold: float = 0.7,
        enable_counterfactual: bool = False,
        counterfactual_limit: int = 3,
        regret_threshold: float = 0.20,
        enable_scenarios: bool = False,
        scenarios_limit: int = 4,
        scenario_recommendation_threshold: float = 0.50,
        enable_foresight: bool = False,
        foresight_limit: int = 5,
        max_horizon: int = 5,
        enable_meta_reasoning: bool = False,
        enable_uncertainty: bool = False,
        enable_information_seeking: bool = False,
    ) -> dict[str, Any]:
        options = PipelineRunOptions(
            execute_mode=execute_mode,
            project_path=project_path,
            limit=limit,
            simulate_before_execute=simulate_before_execute,
            risk_threshold=risk_threshold,
            enable_counterfactual=enable_counterfactual,
            counterfactual_limit=counterfactual_limit,
            regret_threshold=regret_threshold,
            enable_scenarios=enable_scenarios,
            scenarios_limit=scenarios_limit,
            scenario_recommendation_threshold=scenario_recommendation_threshold,
            enable_foresight=enable_foresight,
            foresight_limit=foresight_limit,
            max_horizon=max_horizon,
            enable_meta_reasoning=enable_meta_reasoning,
            enable_uncertainty=enable_uncertainty,
            enable_information_seeking=enable_information_seeking,
        )
        options.validate()
        state = PipelineRunState.create(context, objective, options, self.services.uuid7_generator)
        state.publish(EventType.PIPELINE_RUN_STARTED.value, {"execute_mode": execute_mode})
        try:
            for step in self.steps:
                if not step.execute(state, self.services):
                    break
            return state.result()
        except Exception as exc:
            self._record_failure(state, exc)
            raise

    @staticmethod
    def _record_failure(state: PipelineRunState, exc: Exception) -> None:
        if state.machine.status != RuntimeStatus.FAILED:
            state.transition(RuntimeStatus.FAILED, "pipeline_execution_failed")
        state.publish(
            EventType.PIPELINE_RUN_FAILED.value,
            {"error": "Pipeline execution failed", "error_type": type(exc).__name__},
            caused_by=state.last_event_id,
        )
