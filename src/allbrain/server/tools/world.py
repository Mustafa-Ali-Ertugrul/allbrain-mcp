"""Domain module: world."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.domains.analysis.world import WorldModel
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
)
from allbrain.server.tools._snapshot import maybe_auto_snapshot
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.storage.repository import event_to_read

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
        """Return the current live environment state (CPU, RAM, disk, git branch).

        Reads the running system's resource metrics via psutil and the current
        git branch. Does **not** read the event log or use a learned transition
        model. The ``limit`` argument is accepted for API consistency but has no
        effect on this tool's behaviour.

        Use this to get a snapshot of the host environment before making
        state-dependent decisions.

        Side effects: Appends a WORLD_STATE_OBSERVED event to the log.

        Args:
            limit: Reserved parameter (no-op; kept for schema compatibility).

        Returns:
            Current environment state dict with CPU/RAM/disk metrics, git branch,
            and the associated WORLD_STATE_OBSERVED event record.
        """
        result = observe_world_impl(context, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def simulate_action(
        action: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Simulate the effect of an action using a hardcoded transition model.

        Reads the current live environment state (same as ``observe_world``), then
        runs the action through the world model's transition function. The model
        recognises only four verbs — ``deploy``, ``run_tests``, ``rollback``,
        ``scale`` — and returns fixed fallback scores (success=0.85, risk=0.15,
        cost=0.25) for all other actions. The ``limit`` argument is accepted for
        API consistency but has no effect.

        Use this to preview likely outcomes before executing a real action —
        especially useful for high-risk or irreversible actions. Output is a
        heuristic estimate, not a data-driven prediction.

        Side effects: Appends both a WORLD_STATE_OBSERVED and a WORLD_SIMULATION_RUN
        event to the log. Does not modify real environment state.

        Args:
            action: Description of the action to simulate (e.g., "deploy to production",
                    "grant admin role to user X").
            limit: Reserved parameter (no-op; kept for schema compatibility).

        Returns:
            Simulation result with predicted state changes, risk score, and
            the recorded observation and simulation events.
        """
        result = simulate_action_impl(context, action=action, limit=limit)
        return result.model_dump(mode="json")
