"""Domain module: knowledge."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.belief import BeliefManager
from allbrain.events import EventType
from allbrain.information_seeking import InformationSeekingManager
from allbrain.information_seeking.evaluator import ACTION_VOI_TABLE, InformationSeekingEvaluator
from allbrain.information_seeking.models import (
    INFORMATION_SEEKING_TEMPLATE_VERSION,
    InformationAction,
)
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
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
    observability_project_and_limit,
)
from allbrain.uncertainty import UncertaintyManager, observed_success_rate
from allbrain.uncertainty.models import KnowledgeGap

logger = logging.getLogger(__name__)


def _uncertainty_manager(context: BrainContext, project_path: str) -> UncertaintyManager:
    try:
        events = context.repository.list_events(project_path=context.project_path, limit=5000)
    except Exception:
        events = []
    return UncertaintyManager(calibration_events=events)


def estimate_uncertainty_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
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
            context,
            tool_name="estimate_uncertainty",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=estimate.model_dump(mode="json"))
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def detect_knowledge_gaps_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = DetectKnowledgeGapsInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        manager = _uncertainty_manager(context, project_path)
        gaps = manager.detect_gaps(
            sample_count=0,
            historical=None,
            layer_indicators=[],
            has_feedback=False,
        )
        audit_tool_call(
            context,
            tool_name="detect_knowledge_gaps",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data={"gaps": [gap.model_dump(mode="json") for gap in gaps]})
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def _lookup_uncertainty_gaps(context: BrainContext, decision_id: str, project_path: str) -> list[dict[str, Any]]:
    events = context.repository.list_events(project_path=context.project_path, limit=5000)
    for event in events:
        if (
            event.type == EventType.UNCERTAINTY_ESTIMATED.value
            and isinstance(event.payload, dict)
            and event.payload.get("analysis_id") == decision_id
        ):
            gaps = event.payload.get("knowledge_gaps", [])
            if isinstance(gaps, list):
                return [g for g in gaps if isinstance(g, dict)]
    return []


def identify_information_needs_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = IdentifyInformationNeedsInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        gaps_payload = _lookup_uncertainty_gaps(context, data.decision_id, project_path)
        if not gaps_payload:
            return ToolResult(ok=False, error=f"no knowledge gaps found for decision_id '{data.decision_id}'")
        from allbrain.uncertainty.models import KnowledgeGap

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
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def estimate_information_gain_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
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
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def query_belief_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
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
            context,
            tool_name="query_belief",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
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
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def estimate_information_gain_v2_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
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
            f"action {action_enum.value} belief.info_gain={belief.info_gain:.4f} "
            f"overrode effective gain; cost {cost:.2f}"
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
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def recommend_policy_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        task = kwargs.get("task")
        if not isinstance(task, dict):
            raise UserInputError("task must be a dict")
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        memory = MemoryRetriever(MemoryBuilder().build(events))
        recommendation = RoutingEngine().recommend(task=task, events=events, memory=memory)
        audit_tool_call(
            context,
            tool_name="recommend_policy",
            tool_args={"task": task, "limit": limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=recommendation)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def estimate_uncertainty(
        decision_id: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Estimate uncertainty around a decision.

        Args:
            decision_id: ID of the decision to analyze.
            limit: Maximum number of events to process.

        Returns:
            Tool result as a JSON-serializable dict.
        """
        result = estimate_uncertainty_impl(
            context,
            decision_id=decision_id,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def detect_knowledge_gaps(
        decision_id: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Identify knowledge gaps in the decision context.

        Args:
            decision_id: ID of the decision to analyze.
            limit: Maximum number of events to process.

        Returns:
            Tool result as a JSON-serializable dict.
        """
        result = detect_knowledge_gaps_impl(
            context,
            decision_id=decision_id,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def identify_information_needs(
        decision_id: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Identify what information is needed for a decision.

        Args:
            decision_id: ID of the decision to analyze.
            limit: Maximum number of events to process.

        Returns:
            Tool result as a JSON-serializable dict.
        """
        result = identify_information_needs_impl(
            context,
            decision_id=decision_id,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def estimate_information_gain(
        action: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Estimate information gain from an action.

        Args:
            action: The action to evaluate for information gain.
            limit: Maximum number of events to process.

        Returns:
            Tool result as a JSON-serializable dict.
        """
        result = estimate_information_gain_impl(
            context,
            action=action,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def recommend_policy(
        task: dict[str, Any],
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Recommend a policy based on task and memory.

        Args:
            task: The task definition as a dict.
            limit: Maximum number of events to process.

        Returns:
            Tool result as a JSON-serializable dict.
        """
        result = recommend_policy_impl(context, task=task, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")
