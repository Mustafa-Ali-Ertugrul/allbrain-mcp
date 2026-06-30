"""Domain module: decisions.

NOTE: run_decision_pipeline_impl is re-exported from orchestrator to avoid
duplicate implementation. Historical tests import it from this module, but the
canonical implementation lives in orchestrator.py (which also handles queue
integration for execute_mode="queued_runtime").
"""

from __future__ import annotations

from typing import Any

from allbrain.runtime_core.constants import (
    DEFAULT_COUNTERFACTUAL_LIMIT,
    DEFAULT_FORESIGHT_LIMIT,
    DEFAULT_MAX_HORIZON,
    DEFAULT_PIPELINE_EVENT_LIMIT,
    DEFAULT_REGRET_THRESHOLD,
    DEFAULT_RISK_THRESHOLD,
    DEFAULT_SCENARIO_RECOMMENDATION_THRESHOLD,
    DEFAULT_SCENARIOS_LIMIT,
)
from allbrain.server.context import BrainContext

# Re-export canonical implementation so existing imports keep working.
from allbrain.server.tools.orchestrator import run_decision_pipeline_impl

__all__ = ["register_tools", "run_decision_pipeline_impl"]


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def run_decision_pipeline(
        objective: dict[str, Any],
        execute_mode: str = "event_only",
        limit: int = DEFAULT_PIPELINE_EVENT_LIMIT,
        simulate_before_execute: bool = False,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
        enable_counterfactual: bool = False,
        counterfactual_limit: int = DEFAULT_COUNTERFACTUAL_LIMIT,
        regret_threshold: float = DEFAULT_REGRET_THRESHOLD,
        enable_scenarios: bool = False,
        scenarios_limit: int = DEFAULT_SCENARIOS_LIMIT,
        scenario_recommendation_threshold: float = DEFAULT_SCENARIO_RECOMMENDATION_THRESHOLD,
        enable_foresight: bool = False,
        foresight_limit: int = DEFAULT_FORESIGHT_LIMIT,
        max_horizon: int = DEFAULT_MAX_HORIZON,
        enable_meta_reasoning: bool = False,
        enable_uncertainty: bool = False,
        enable_information_seeking: bool = False,
    ) -> dict[str, Any]:
        result = run_decision_pipeline_impl(
            context,
            objective=objective,
            execute_mode=execute_mode,
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
        return result.model_dump(mode="json")
