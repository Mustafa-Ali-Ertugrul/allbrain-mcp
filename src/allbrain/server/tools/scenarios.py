"""Domain module: scenarios."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.events import EventType
from allbrain.models.schemas import (
    EvaluateScenariosInput,
    GenerateScenariosInput,
    ToolResult,
    UserInputError,
)
from allbrain.scenarios import ScenarioAnalysis, ScenarioEngine
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
)
from allbrain.world import WorldModel

logger = logging.getLogger(__name__)


def _publish_scenario_events(
    context: BrainContext,
    bound_session_id: int,
    project_path: str,
    analysis: ScenarioAnalysis,
    action: str,
) -> None:
    analysis_payload = analysis.model_dump(mode="json")
    generated_event = context.repository.append_event(
        project_path=project_path,
        session_id=bound_session_id,
        type=EventType.SCENARIO_GENERATED.value,
        source="scenarios",
        payload={
            "action": action,
            "templates": [item.scenario for item in analysis.results],
            "template_version": analysis.template_version,
            "analysis_id": analysis_payload["analysis_id"],
        },
    )
    last_id = generated_event.id
    for result in analysis.results:
        ev_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.SCENARIO_EVALUATED.value,
            source="scenarios",
            payload={
                "analysis_id": analysis_payload["analysis_id"],
                "scenario": result.scenario,
                "prediction": result.prediction.model_dump(mode="json"),
                "confidence": result.confidence,
            },
            caused_by=last_id,
            impact_score=result.confidence,
        )
        last_id = ev_event.id
    rationale = (
        f"best={analysis.best_case.prediction.success_probability:.2f} "
        f"vs expected={analysis.expected_case.prediction.success_probability:.2f}, "
        f"spread={analysis.prediction_spread:.2f}"
    )
    context.repository.append_event(
        project_path=project_path,
        session_id=bound_session_id,
        type=EventType.SCENARIO_RECOMMENDED.value,
        source="scenarios",
        payload={
            "analysis_id": analysis_payload["analysis_id"],
            "best_case": analysis.best_case.model_dump(mode="json"),
            "expected_case": analysis.expected_case.model_dump(mode="json"),
            "rationale": rationale,
            "template_version": analysis.template_version,
        },
        caused_by=last_id,
        impact_score=analysis.prediction_spread,
    )


def generate_scenarios_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = GenerateScenariosInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        world_model = WorldModel()
        engine = ScenarioEngine()
        current_state = world_model.observe()
        context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="scenarios",
            payload=current_state.model_dump(mode="json"),
        )
        analysis = engine.analyze(current_state, data.action, limit=data.scenarios_limit)
        _publish_scenario_events(context, bound_session_id, project_path, analysis, data.action)
        audit_tool_call(
            context,
            tool_name="generate_scenarios",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(ok=True, data=analysis.model_dump(mode="json"))
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def evaluate_scenarios_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = EvaluateScenariosInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        world_model = WorldModel()
        engine = ScenarioEngine()
        current_state = world_model.observe()
        context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="scenarios",
            payload=current_state.model_dump(mode="json"),
        )
        analysis = engine.evaluate_custom(current_state, data.action, list(data.scenarios))
        _publish_scenario_events(context, bound_session_id, project_path, analysis, data.action)
        audit_tool_call(
            context,
            tool_name="evaluate_scenarios",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(ok=True, data=analysis.model_dump(mode="json"))
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def generate_scenarios(
        action: str,
        limit: int = 5000,
        scenarios_limit: int = 4,
    ) -> dict[str, Any]:
        result = generate_scenarios_impl(
            context,
            action=action,
            limit=limit,
            scenarios_limit=scenarios_limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def evaluate_scenarios(
        action: str,
        scenarios: list[dict[str, Any]],
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = evaluate_scenarios_impl(
            context,
            action=action,
            scenarios=scenarios,
            limit=limit,
        )
        return result.model_dump(mode="json")
