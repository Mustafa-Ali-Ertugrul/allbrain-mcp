"""Domain module: world."""
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
    ObserveWorldInput,
    SimulateActionInput,
)
from allbrain.events import EventType
from allbrain.world import WorldModel
from allbrain.storage.repository import event_to_read

logger = logging.getLogger(__name__)


def observe_world_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = ObserveWorldInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        world_model = WorldModel()
        state = world_model.observe()
        event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="world",
            payload=state.model_dump(mode="json"),
        )
        audit_tool_call(
            context,
            tool_name="observe_world",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(
            ok=True,
            data={"state": state.model_dump(mode="json"), "event": event_to_read(event).model_dump(mode="json")},
        )
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def simulate_action_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = SimulateActionInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        world_model = WorldModel()
        state = world_model.observe()
        observation_event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="world",
            payload=state.model_dump(mode="json"),
        )
        sim_result = world_model.simulate(data.action, state)
        sim_event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_SIMULATION_RUN.value,
            source="world",
            payload=sim_result.model_dump(mode="json"),
            caused_by=observation_event.id,
            impact_score=sim_result.prediction.risk,
        )
        audit_tool_call(
            context,
            tool_name="simulate_action",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(
            ok=True,
            data={
                "observation_event": event_to_read(observation_event).model_dump(mode="json"),
                "simulation_event": event_to_read(sim_event).model_dump(mode="json"),
                "simulation": sim_result.model_dump(mode="json"),
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
    def observe_world(limit: int = 5000) -> dict[str, Any]:
        result = observe_world_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def simulate_action(
        action: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = simulate_action_impl(context, action=action, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")
