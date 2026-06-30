"""Domain module: counterfactual."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
)
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.models.schemas import (
    ToolResult,
    UserInputError,
    CounterfactualInput,
    AlternativeRankingInput,
)
from allbrain.events import EventType
from allbrain.world import WorldModel
from allbrain.counterfactual import CounterfactualEngine, AlternativeRanker
from allbrain.counterfactual.models import recommendation_severity

logger = logging.getLogger(__name__)


def generate_counterfactual_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = CounterfactualInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        world_model = WorldModel()
        engine = CounterfactualEngine()
        current_state = world_model.observe()
        observation_event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="counterfactual",
            payload=current_state.model_dump(mode="json"),
        )
        generated_payload: dict[str, Any] = {"action": data.action, "alternatives": []}
        unknown = not engine.generator.generate(data.action)
        if unknown:
            generated_payload["reason"] = "unknown_action"
        generated_event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.COUNTERFACTUAL_GENERATED.value,
            source="counterfactual",
            payload=generated_payload,
            caused_by=observation_event.id,
        )
        alternatives = engine.generator.generate(data.action)[: data.counterfactual_limit]
        results_payloads: list[dict[str, Any]] = []
        for alternative in alternatives:
            result = engine.evaluator.compare(current_state, data.action, alternative)
            context.repository.append_event(
                project_path=context.project_path,
                session_id=bound_session_id,
                type=EventType.COUNTERFACTUAL_EVALUATED.value,
                source="counterfactual",
                payload=result.model_dump(mode="json"),
                caused_by=generated_event.id,
                impact_score=result.improvement,
            )
            results_payloads.append(result.model_dump(mode="json"))
        best_payload: dict[str, Any] | None = None
        recommendation_payload: dict[str, Any] | None = None
        if results_payloads:
            best_payload = max(results_payloads, key=lambda item: item["improvement"])
            if best_payload["improvement"] >= 0.20:
                severity = recommendation_severity(best_payload["improvement"])
                recommendation_payload = {"best": best_payload, "threshold": 0.20, "severity": severity}
                context.repository.append_event(
                    project_path=context.project_path,
                    session_id=bound_session_id,
                    type=EventType.COUNTERFACTUAL_RECOMMENDATION.value,
                    source="counterfactual",
                    payload=recommendation_payload,
                    caused_by=generated_event.id,
                    impact_score=best_payload["improvement"],
                )
        summary = {
            "action": data.action,
            "alternatives": alternatives,
            "unknown_action": unknown,
            "results": results_payloads,
            "best": best_payload,
            "decision_regret": best_payload["regret"] if best_payload else 0.0,
            "recommendation": recommendation_payload,
        }
        audit_tool_call(
            context,
            tool_name="generate_counterfactual",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(ok=True, data=summary)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def rank_alternatives_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = AlternativeRankingInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        world_model = WorldModel()
        current_state = world_model.observe()
        ranker = AlternativeRanker()
        ranked = ranker.rank(current_state, list(data.actions))
        audit_tool_call(
            context,
            tool_name="rank_alternatives",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(
            ok=True,
            data={
                "state": current_state.model_dump(mode="json"),
                "ranked": [item.model_dump(mode="json") for item in ranked],
            },
        )
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def generate_counterfactual(
        action: str,
        limit: int = 5000,
        counterfactual_limit: int = 3,
    ) -> dict[str, Any]:
        result = generate_counterfactual_impl(
            context,
            action=action,
            limit=limit,
            counterfactual_limit=counterfactual_limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def rank_alternatives(
        actions: list[str],
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = rank_alternatives_impl(context, actions=actions, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")
