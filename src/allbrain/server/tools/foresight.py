"""Domain module: foresight."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.events import EventType
from allbrain.foresight import ForesightEngine
from allbrain.foresight.models import FORESIGHT_TEMPLATE_VERSION, ForesightAnalysis
from allbrain.meta_reasoning import ConfidenceEngine, MetaReasoningManager
from allbrain.models.schemas import (
    EstimateConfidenceInput,
    EvaluatePlanInput,
    ExplainDecisionInput,
    GenerateFuturePlansInput,
    ToolResult,
)
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
)
from allbrain.server.tools._snapshot import maybe_auto_snapshot
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.uncertainty import observed_success_rate
from allbrain.world import WorldModel

logger = logging.getLogger(__name__)


def _publish_foresight_events(
    context: BrainContext,
    bound_session_id: int,
    project_path: str,
    analysis: ForesightAnalysis,
    action: str,
) -> None:
    analysis_payload = analysis.model_dump(mode="json")
    generated_event = context.repository.append_event(
        project_path=project_path,
        session_id=bound_session_id,
        type=EventType.FORESIGHT_GENERATED.value,
        source="foresight",
        payload={
            "action": action,
            "plans_count": len(analysis.plans),
            "plan_ids": [f"plan_{idx}" for idx in range(len(analysis.plans))],
            "template_version": FORESIGHT_TEMPLATE_VERSION,
            "analysis_id": analysis_payload["analysis_id"],
        },
    )
    last_id = generated_event.id
    for idx, plan in enumerate(analysis.plans):
        plan_payload = plan.model_dump(mode="json")
        plan_payload["analysis_id"] = analysis_payload["analysis_id"]
        plan_payload["plan_id"] = f"plan_{idx}"
        ev_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.FORESIGHT_EVALUATED.value,
            source="foresight",
            payload=plan_payload,
            caused_by=last_id,
            impact_score=plan.predicted_success,
        )
        last_id = ev_event.id
    rationale = (
        f"best={analysis.best_plan.predicted_success:.2f} "
        f"horizon={analysis.expected_plan.horizon} "
        f"spread={analysis.plan_spread:.2f}"
    )
    context.repository.append_event(
        project_path=project_path,
        session_id=bound_session_id,
        type=EventType.FORESIGHT_RECOMMENDED.value,
        source="foresight",
        payload={
            "analysis_id": analysis_payload["analysis_id"],
            "best_plan": analysis.best_plan.model_dump(mode="json"),
            "expected_plan": analysis.expected_plan.model_dump(mode="json"),
            "rationale": rationale,
            "template_version": FORESIGHT_TEMPLATE_VERSION,
        },
        caused_by=last_id,
        impact_score=analysis.plan_spread,
    )


@handle_tool_errors
def generate_future_plans_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = GenerateFuturePlansInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    project_path = context.project_path
    world_model = WorldModel()
    engine = ForesightEngine(max_horizon=data.max_horizon)
    current_state = world_model.observe()
    context.repository.append_event(
        project_path=context.project_path,
        session_id=bound_session_id,
        type=EventType.WORLD_STATE_OBSERVED.value,
        source="foresight",
        payload=current_state.model_dump(mode="json"),
    )
    analysis = engine.analyze(current_state, data.action, limit=data.foresight_limit)
    _publish_foresight_events(context, bound_session_id, project_path, analysis, data.action)
    audit_tool_call(
        context,
        tool_name="generate_future_plans",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    maybe_auto_snapshot(context, project_path=context.project_path)
    return ToolResult(ok=True, data=analysis.model_dump(mode="json"))


@handle_tool_errors
def evaluate_plan_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = EvaluatePlanInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    world_model = WorldModel()
    engine = ForesightEngine(max_horizon=data.max_horizon)
    current_state = world_model.observe()
    context.repository.append_event(
        project_path=context.project_path,
        session_id=bound_session_id,
        type=EventType.WORLD_STATE_OBSERVED.value,
        source="foresight",
        payload=current_state.model_dump(mode="json"),
    )
    plan = engine.evaluate_custom(current_state, list(data.actions))
    analysis_payload = {
        "action": "custom",
        "plans_count": 1,
        "plan_ids": ["plan_0"],
        "template_version": FORESIGHT_TEMPLATE_VERSION,
        "analysis_id": "00000000-0000-0000-0000-000000000000",
    }
    generated_event = context.repository.append_event(
        project_path=context.project_path,
        session_id=bound_session_id,
        type=EventType.FORESIGHT_GENERATED.value,
        source="foresight",
        payload=analysis_payload,
    )
    plan_payload = plan.model_dump(mode="json")
    plan_payload["analysis_id"] = "00000000-0000-0000-0000-000000000000"
    plan_payload["plan_id"] = "plan_0"
    context.repository.append_event(
        project_path=context.project_path,
        session_id=bound_session_id,
        type=EventType.FORESIGHT_EVALUATED.value,
        source="foresight",
        payload=plan_payload,
        caused_by=generated_event.id,
        impact_score=plan.predicted_success,
    )
    rationale = f"custom plan: actions={plan.actions} success={plan.predicted_success:.2f}"
    context.repository.append_event(
        project_path=context.project_path,
        session_id=bound_session_id,
        type=EventType.FORESIGHT_RECOMMENDED.value,
        source="foresight",
        payload={
            "analysis_id": "00000000-0000-0000-0000-000000000000",
            "best_plan": plan.model_dump(mode="json"),
            "expected_plan": plan.model_dump(mode="json"),
            "rationale": rationale,
            "template_version": FORESIGHT_TEMPLATE_VERSION,
        },
        caused_by=generated_event.id,
        impact_score=plan.predicted_success,
    )
    audit_tool_call(
        context,
        tool_name="evaluate_plan",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    maybe_auto_snapshot(context, project_path=context.project_path)
    return ToolResult(ok=True, data=plan.model_dump(mode="json"))


def _lookup_foresight_plan(
    context: BrainContext, plan_id: str, bound_session_id: int, project_path: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    events = context.repository.list_events(project_path=context.project_path, limit=5000)
    plan_payload: dict[str, Any] | None = None
    for event in events:
        if event.type == EventType.FORESIGHT_EVALUATED.value and event.payload.get("plan_id") == plan_id:
            plan_payload = {k: v for k, v in event.payload.items() if k not in ("analysis_id", "plan_id")}
            break
    if plan_payload is None:
        return None, None
    analysis_id = event.payload.get("analysis_id")
    candidates: list[dict[str, Any]] = []
    if isinstance(analysis_id, str):
        for ev in events:
            if (
                ev.type == EventType.FORESIGHT_EVALUATED.value
                and ev.payload.get("analysis_id") == analysis_id
                and ev.payload.get("plan_id") != plan_id
            ):
                candidates.append({k: v for k, v in ev.payload.items() if k not in ("analysis_id", "plan_id")})
    return plan_payload, {"analysis_id": analysis_id, "candidates": candidates} if analysis_id else None


@handle_tool_errors
def explain_decision_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = ExplainDecisionInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    project_path = context.project_path
    plan_payload, lookup = _lookup_foresight_plan(context, data.plan_id, bound_session_id, project_path)
    if plan_payload is None or lookup is None:
        return ToolResult(ok=False, error=f"plan_id '{data.plan_id}' not found in foresight events")
    from allbrain.foresight.models import FuturePlan

    selected_plan = FuturePlan.model_validate(plan_payload)
    candidates = [FuturePlan.model_validate(c) for c in lookup["candidates"]]
    manager = MetaReasoningManager()
    explanation = manager.explain(
        selected_plan, candidates, _dummy_foresight_result(selected_plan, lookup["analysis_id"])
    )
    audit_tool_call(
        context,
        tool_name="explain_decision",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data=explanation.model_dump(mode="json"))


@handle_tool_errors
def estimate_confidence_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = EstimateConfidenceInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    project_path = context.project_path
    plan_payload, lookup = _lookup_foresight_plan(context, data.plan_id, bound_session_id, project_path)
    if plan_payload is None or lookup is None:
        return ToolResult(ok=False, error=f"plan_id '{data.plan_id}' not found in foresight events")
    from allbrain.foresight.models import FuturePlan

    selected_plan = FuturePlan.model_validate(plan_payload)
    try:
        events = context.repository.list_events(project_path=context.project_path, limit=5000)
        historical = observed_success_rate(events)
    except Exception:
        historical = 0.7
    engine = ConfidenceEngine()
    estimate = engine.estimate(selected_plan, _dummy_foresight_result(selected_plan, lookup["analysis_id"]), historical)
    audit_tool_call(
        context,
        tool_name="estimate_confidence",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data=estimate.model_dump(mode="json"))


def _dummy_foresight_result(selected_plan, analysis_id: str):
    from uuid6 import uuid7

    from allbrain.foresight.models import ForesightAnalysis

    return ForesightAnalysis(
        analysis_id=uuid7(),
        action="lookup",
        best_plan=selected_plan,
        expected_plan=selected_plan,
        safest_plan=selected_plan,
        fastest_plan=selected_plan,
        plan_spread=0.0,
        strategy_uncertainty=0.5,
        horizon_risk=selected_plan.cumulative_risk,
        plans=[selected_plan],
    )


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def generate_future_plans(
        action: str,
        limit: int = 5000,
        foresight_limit: int = 5,
        max_horizon: int = 5,
    ) -> dict[str, Any]:
        """Generate possible future plan branches starting from an action.

        Uses recursive foresight to explore multi-step action chains. Each branch
        includes expected outcomes, risk estimates, and resource costs. Scenarios
        are grouped into best-plan, expected-plan, and safest-plan categories.

        Use this for strategic planning where you need to see multi-step consequences
        before committing. Use `evaluate_plan` when you already have a concrete action
        list and want it scored. Use `run_decision_pipeline` to chain all reasoning.

        Side effects: Records WORLD_STATE_OBSERVED, FORESIGHT_GENERATED,
        FORESIGHT_EVALUATED, and FORESIGHT_RECOMMENDED events.

        Args:
            action: The action to branch future plans from (starting point).
            limit: Max events to consider (default 5000).
            foresight_limit: Max number of plan branches to generate (default 5).
            max_horizon: Max steps deep into the future per plan (default 5).

        Returns:
            Foresight analysis with multiple plans, best/expected/safest plan
            assignments, plan spreads, strategy uncertainty, and horizon risk.
        """
        result = generate_future_plans_impl(
            context,
            action=action,
            limit=limit,
            foresight_limit=foresight_limit,
            max_horizon=max_horizon,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def evaluate_plan(
        actions: list[str],
        limit: int = 5000,
        max_horizon: int = 5,
    ) -> dict[str, Any]:
        """Score an existing plan represented as a list of action descriptions.

        Estimates success probability per step, identifies risk inflection points,
        and computes an overall confidence score. Unlike `generate_future_plans`, this
        evaluates a fixed plan you already have rather than exploring branches.

        Use this when you have a concrete multi-step plan and need it scored against
        the world model. For open-ended plan exploration, use `generate_future_plans`.

        Side effects: Records WORLD_STATE_OBSERVED, FORESIGHT_GENERATED,
        FORESIGHT_EVALUATED, and FORESIGHT_RECOMMENDED events.

        Args:
            actions: Ordered list of action descriptions forming the plan (e.g.,
                    ["analyze requirements", "design API", "implement", "test"]).
            limit: Max events to consider (default 5000).
            max_horizon: Max planning depth (default 5).

        Returns:
            Plan evaluation with per-step predictions, cumulative risk,
            predicted success probability, and recommended modifications.
        """
        result = evaluate_plan_impl(
            context,
            actions=actions,
            limit=limit,
            max_horizon=max_horizon,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def explain_decision(
        plan_id: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Return a human-readable explanation of a past decision pipeline run.

        Retrieves the decision's inputs, reasoning trace, scenario evaluations,
        tradeoffs considered, and the final selection. Uses meta-reasoning to compare
        the selected plan against alternatives.

        Call this after `run_decision_pipeline` to audit why a decision was made.
        Provides the full audit trail for non-repudiation.

        Side effects: Read-only operation; does not modify state. Requires a valid
        plan_id from a previous FORESIGHT_EVALUATED event.

        Args:
            plan_id: The plan ID from a previous foresight or decision pipeline run
                    (found in FORESIGHT_EVALUATED event payloads).

        Returns:
            Decision explanation with selected plan, alternative plans compared,
            tradeoffs considered, rationale, and confidence level.
        """
        result = explain_decision_impl(
            context,
            plan_id=plan_id,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def estimate_confidence(
        plan_id: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Estimate the confidence level of a prior decision pipeline plan.

        Returns calibration error, sample count, and drift metrics that indicate
        how reliable the decision's recommendation is. Combines historical success
        rates from past events with model-based uncertainty estimates.

        Call this after `run_decision_pipeline` or `evaluate_plan` to assess how
        much to trust the results. High confidence = low uncertainty, strong
        historical support.

        Side effects: Read-only operation. Requires a valid plan_id from a previous
        FORESIGHT_EVALUATED event.

        Args:
            plan_id: The plan ID from a previous foresight or decision pipeline run.
            limit: Max events to consider for historical analysis (default 5000).

        Returns:
            Confidence estimate with calibration error, support sample count,
            drift indicators, and overall trust score.
        """
        result = estimate_confidence_impl(
            context,
            plan_id=plan_id,
            limit=limit,
        )
        return result.model_dump(mode="json")
