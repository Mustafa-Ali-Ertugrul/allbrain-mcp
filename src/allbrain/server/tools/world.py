"""Domain module: world."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import (
    ObserveWorldInput,
    SimulateActionInput,
    ToolResult,
)
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
)
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.storage.repository import event_to_read
from allbrain.world import WorldModel

logger = logging.getLogger(__name__)


@handle_tool_errors
def observe_world_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = ObserveWorldInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
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


@handle_tool_errors
def simulate_action_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = SimulateActionInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
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


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def observe_world(limit: int = 5000) -> dict[str, Any]:
        """Return the current environment state built from the event log.

        Observes the project's world model — the learned transition model derived from
        past agent actions and events. Returns the predicted current state based on all
        stored observations.

        Use this before making state-dependent decisions or to understand the environment
        context for agent actions.

        Side effects: Appends a WORLD_STATE_OBSERVED event to the log. Read-only on
        the world model itself.

        Args:
            limit: Maximum number of events to process for state reconstruction (default 5000).

        Returns:
            Current world state dict with environment context, recent observations,
            and the associated event record.
        """
        result = observe_world_impl(context, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def simulate_action(
        action: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Simulate the effect of an action using the learned world model.

        Predicts how the environment state would change if the described action were
        taken. Uses the world model's transition function learned from past observations.
        Complements `generate_counterfactual` and `generate_scenarios` by focusing
        on environment state changes rather than agent decisions.

        Use this to preview likely outcomes before executing a real action — especially
        useful for high-risk or irreversible actions.

        Side effects: Appends both a WORLD_STATE_OBSERVED and a WORLD_SIMULATION_RUN
        event to the log. Does not modify real environment state.

        Args:
            action: Description of the action to simulate (e.g., "deploy to production",
                   "grant admin role to user X").
            limit: Maximum number of events to process (default 5000).

        Returns:
            Simulation result with predicted state changes, risk score, and
            the recorded observation and simulation events.
        """
        result = simulate_action_impl(context, action=action, limit=limit)
        return result.model_dump(mode="json")
