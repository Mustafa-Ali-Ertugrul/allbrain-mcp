"""Domain module: knowledge."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.belief import BeliefManager
from allbrain.domains.reasoning.information_seeking import InformationSeekingManager
from allbrain.domains.reasoning.information_seeking.evaluator import ACTION_VOI_TABLE, InformationSeekingEvaluator
from allbrain.domains.reasoning.information_seeking.models import (
    INFORMATION_SEEKING_TEMPLATE_VERSION,
    InformationAction,
)
from allbrain.domains.reasoning.uncertainty import UncertaintyManager, observed_success_rate
from allbrain.events import EventType
from allbrain.memory import MemoryBuilder, MemoryRetriever
from allbrain.models.schemas import (
    DetectKnowledgeGapsInput,
    EstimateInformationGainInput,
    EstimateInformationGainV2Input,
    EstimateUncertaintyInput,
    IdentifyInformationNeedsInput,
    QueryBeliefInput,
    ToolResult,
    UserInputError,
)
from allbrain.policy import RoutingEngine
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import audit_tool_call, bind_session_id
from allbrain.server.tools._tasks import observability_project_and_limit
from allbrain.server.tools.decorators import handle_tool_errors

logger = logging.getLogger(__name__)


def _uncertainty_manager(context: BrainContext, project_path: str) -> UncertaintyManager:
    try:
        events = context.repository.list_events(project_path=context.project_path, limit=5000)
    except Exception:
        events = []
    return UncertaintyManager(calibration_events=events)


@handle_tool_errors
def estimate_uncertainty_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = EstimateUncertaintyInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    project_path = context.project_path
    manager = _uncertainty_manager(context, project_path)
    historical = observed_success_rate(manager._calibration_events) if manager._calibration_events else 0.7
    estimate = manager.estimate(
        historical=historical,
        evidence=0.7,
        layer_indicators=[],
        sample_count=1,
        sample_quality=0.7,
        has_feedback=False,
        analysis_id=data.decision_id,
    )
    audit_tool_call(
        context, tool_name="estimate_uncertainty", tool_args=data.model_dump(mode="json"), session_id=bound_session_id
    )
    return ToolResult(ok=True, data=estimate.model_dump(mode="json"))


@handle_tool_errors
def detect_knowledge_gaps_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = DetectKnowledgeGapsInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    project_path = context.project_path
    manager = _uncertainty_manager(context, project_path)
    gaps = manager.detect_gaps(sample_count=0, historical=None, layer_indicators=[], has_feedback=False)
    audit_tool_call(
        context, tool_name="detect_knowledge_gaps", tool_args=data.model_dump(mode="json"), session_id=bound_session_id
    )
    return ToolResult(ok=True, data={"gaps": [gap.model_dump(mode="json") for gap in gaps]})


def _lookup_uncertainty_gaps(context: BrainContext, decision_id: str, project_path: str) -> list[dict[str, Any]]:
    events = context.repository.list_events(project_path=context.project_path, limit=5000)
    for event in events:
        if (
            event.type == EventType.UNCERTAINTY_ESTIMATED.value
            and isinstance(event.payload, dict)
            and (event.payload.get("analysis_id") == decision_id)
        ):
            gaps = event.payload.get("knowledge_gaps", [])
            if isinstance(gaps, list):
                return [g for g in gaps if isinstance(g, dict)]
    return []


@handle_tool_errors
def identify_information_needs_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = IdentifyInformationNeedsInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    project_path = context.project_path
    gaps_payload = _lookup_uncertainty_gaps(context, data.decision_id, project_path)
    if not gaps_payload:
        return ToolResult(ok=False, error=f"no knowledge gaps found for decision_id '{data.decision_id}'")
    from allbrain.domains.reasoning.uncertainty.models import KnowledgeGap

    gaps = [KnowledgeGap.model_validate(g) for g in gaps_payload]
    manager = InformationSeekingManager()
    plan = manager.analyze(gaps, analysis_id=data.decision_id or None)
    audit_tool_call(
        context,
        tool_name="identify_information_needs",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data=plan.model_dump(mode="json"))


@handle_tool_errors
def estimate_information_gain_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = EstimateInformationGainInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    try:
        action_enum = InformationAction(data.action)
    except ValueError:
        return ToolResult(ok=False, error=f"unknown action '{data.action}'")
    base = ACTION_VOI_TABLE.get(action_enum.value, {"gain": 0.0, "cost": 0.0})
    rationale = f"action {action_enum.value} baseline gain {base['gain']} cost {base['cost']}"
    audit_tool_call(
        context,
        tool_name="estimate_information_gain",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(
        ok=True,
        data={
            "action": action_enum.value,
            "gain": base["gain"],
            "cost": base["cost"],
            "voi": max(0.0, base["gain"] - base["cost"]),
            "rationale": rationale,
            "template_version": INFORMATION_SEEKING_TEMPLATE_VERSION,
        },
    )


@handle_tool_errors
def query_belief_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = QueryBeliefInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    try:
        events = context.repository.list_events(
            project_path=context.project_path, limit=data.limit, session_id=bound_session_id
        )
    except Exception:
        events = []
    manager = BeliefManager(prior_alpha=data.prior_alpha, prior_beta=data.prior_beta)
    belief = manager.query(events, context_key=data.context_key)
    audit_tool_call(
        context, tool_name="query_belief", tool_args=data.model_dump(mode="json"), session_id=bound_session_id
    )
    return ToolResult(
        ok=True,
        data={
            "context_key": belief.context_key,
            "analysis_id": belief.analysis_id,
            "alpha": belief.alpha,
            "beta": belief.beta,
            "mean": belief.mean,
            "variance": belief.variance,
            "info_gain": belief.info_gain,
            "successes": belief.successes,
            "failures": belief.failures,
            "blocked": belief.blocked,
            "sample_count": belief.sample_count,
            "template_version": belief.template_version,
        },
    )


@handle_tool_errors
def estimate_information_gain_v2_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = EstimateInformationGainV2Input.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    try:
        action_enum = InformationAction(data.action)
    except ValueError:
        return ToolResult(ok=False, error=f"unknown action '{data.action}'")
    try:
        events = context.repository.list_events(
            project_path=context.project_path, limit=data.limit, session_id=bound_session_id
        )
    except Exception:
        events = []
    manager = BeliefManager(prior_alpha=data.prior_alpha, prior_beta=data.prior_beta)
    belief = manager.query(events, context_key=data.context_key)
    ACTION_VOI_TABLE.get(action_enum.value, {"gain": 0.0, "cost": 0.0})
    evaluator = InformationSeekingEvaluator()
    gain, cost, voi = evaluator.evaluate(action_enum, [], belief=belief)
    rationale = (
        f"action {action_enum.value} belief.info_gain={belief.info_gain:.4f} overrode effective gain; cost {cost:.2f}"
    )
    audit_tool_call(
        context,
        tool_name="estimate_information_gain_v2",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(
        ok=True,
        data={
            "action": action_enum.value,
            "context_key": belief.context_key,
            "analysis_id": belief.analysis_id,
            "belief_info_gain": belief.info_gain,
            "belief_mean": belief.mean,
            "belief_sample_count": belief.sample_count,
            "gain": gain,
            "cost": cost,
            "voi": voi,
            "rationale": rationale,
            "template_version": INFORMATION_SEEKING_TEMPLATE_VERSION,
        },
    )


@handle_tool_errors
def recommend_policy_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    task = kwargs.get("task")
    if not isinstance(task, dict):
        raise UserInputError("task must be a dict")
    project_path, limit = observability_project_and_limit(context, kwargs)
    bound_session_id = bind_session_id(context, None)
    events = context.repository.list_events(project_path=context.project_path, limit=limit)
    memory = MemoryRetriever(MemoryBuilder().build(events))
    recommendation = RoutingEngine().recommend(task=task, events=events, memory=memory)
    audit_tool_call(
        context, tool_name="recommend_policy", tool_args={"task": task, "limit": limit}, session_id=bound_session_id
    )
    return ToolResult(ok=True, data=recommendation)


def register_tools(mcp, context: BrainContext) -> None:

    @mcp.tool
    def estimate_uncertainty(decision_id: str, limit: int = 5000) -> dict[str, Any]:
        """Estimate epistemic and aleatoric uncertainty around a prior decision.

        Returns calibrated uncertainty scores â€” separate epistemic (model knowledge)
        and aleatoric (inherent randomness) components â€” along with drift metrics.
        High uncertainty suggests more information gathering before acting.

        Call this after `run_decision_pipeline` to understand reliability of outputs.
        Use `detect_knowledge_gaps` to identify what specific information is missing.

        Side effects: Read-only operation. Analyzes calibration events from the log.

        Args:
            decision_id: ID of the decision to analyze for uncertainty.
            limit: Max events to consider for calibration (default 5000).

        Returns:
            Uncertainty estimate with epistemic and aleatoric scores,
            calibration error, sample count, and drift indicators.
        """
        result = estimate_uncertainty_impl(context, decision_id=decision_id, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def detect_knowledge_gaps(decision_id: str, limit: int = 5000) -> dict[str, Any]:
        """Identify missing information that would improve a decision's quality.

        Analyzes the decision context and flags specific information items that, if
        gathered, would most reduce uncertainty. Returns actionable knowledge gaps
        with prioritization scores.

        Use this when uncertainty is high and you need concrete suggestions for what
        additional data to collect. Less detailed than `identify_information_needs`
        which produces a structured investigation plan from these gaps.

        Side effects: Read-only operation.

        Args:
            decision_id: ID of the decision to analyze for knowledge gaps.
            limit: Max events to consider (default 5000).

        Returns:
            List of knowledge gaps with descriptions, priority scores, and
            recommended information sources for each gap.
        """
        result = detect_knowledge_gaps_impl(context, decision_id=decision_id, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def identify_information_needs(decision_id: str, limit: int = 5000) -> dict[str, Any]:
        """List specific information items needed to make a well-informed decision.

        Returns actionable questions to resolve, data sources to consult, and analyses
        to run â€” structured as an investigation plan. Builds on knowledge gaps found
        by `detect_knowledge_gaps` and prioritizes by expected information gain.

        Use during decision preparation to systematically enumerate what must be
        learned before committing to a course of action. Call after
        `detect_knowledge_gaps` for a deeper investigation plan.

        Side effects: Read-only operation. Requires prior detected knowledge gaps.

        Args:
            decision_id: ID of the decision whose information needs to analyze.
            limit: Max events to consider (default 5000).

        Returns:
            Investigation plan with prioritized information needs, recommended data
            sources, expected information gains, and investigation costs.
        """
        result = identify_information_needs_impl(context, decision_id=decision_id, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def estimate_information_gain(action: str, limit: int = 5000) -> dict[str, Any]:
        """Predict how much new information a proposed investigation action would yield.

        Models the expected information gain from performing the specified action,
        based on the Value of Information (VOI) table. Returns gain, cost, and net
        value of information.

        Use this to prioritize actions by their learning value. High-gain actions
        are worth taking early in exploration. For a belief-aware version that
        considers posterior distributions, use `estimate_information_gain_v2`.

        Side effects: Read-only operation. Uses static VOI table lookup.

        Args:
            action: The investigation action to evaluate (e.g., "run_experiment",
                   "query_database", "interview_stakeholder").
            limit: Max events to consider (default 5000).

        Returns:
            Information gain estimate with expected gain, cost, net VOI,
            and baseline rationale.
        """
        result = estimate_information_gain_impl(context, action=action, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def recommend_policy(task: dict[str, Any], limit: int = 5000) -> dict[str, Any]:
        """Recommend an action policy for a given task based on past experience.

        Considers agent capabilities, task requirements, historical success rates,
        and learned strategies from similar past tasks. Uses the RoutingEngine with
        memory retrieval to find relevant precedents.

        Use this when planning a new task and you want a data-driven suggestion for
        which approach or agent is likely to succeed. Particularly useful in
        multi-agent systems for task routing decisions.

        Side effects: Read-only operation. Builds memory from event log.

        Args:
            task: The task definition dict with at minimum a description, and
                 optionally required capabilities, priority, and constraints.
            limit: Max events to consider (default 5000).

        Returns:
            Policy recommendation with suggested agent, approach, success
            probability estimate, and relevant historical precedents.
        """
        result = recommend_policy_impl(context, task=task, limit=limit)
        return result.model_dump(mode="json")

