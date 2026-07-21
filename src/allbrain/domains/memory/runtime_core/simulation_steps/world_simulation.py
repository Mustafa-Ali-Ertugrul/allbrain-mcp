"""World simulation step extracted from SimulationOrchestrator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from allbrain.domains.memory.runtime_core.contracts import RuntimeContext
from allbrain.domains.memory.runtime_core.event_bus import RuntimeEventBus
from allbrain.domains.memory.runtime_core.observability import ObservabilityCollector
from allbrain.events import EventType
from allbrain.models.schemas import EventRead

if TYPE_CHECKING:
    from allbrain.domains.analysis.world import WorldModel

logger = logging.getLogger(__name__)


def execute(
    bus: RuntimeEventBus,
    context: RuntimeContext,
    project_path: str | None,
    objective: dict[str, Any],
    caused_by: str,
    risk_threshold: float,
    limit: int,
    world: WorldModel,
) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
    """Run world simulation step with learning from historical events.

    Args:
        bus: Event bus for publishing events
        context: Brain context with repository
        project_path: Project path for event history
        objective: Objective dictionary
        caused_by: Causal event ID
        risk_threshold: Risk threshold for blocking
        limit: Max events to learn from
        world: World model for state observation and simulation

    Returns:
        Tuple of (simulation payload, last event ID, emitted events)
    """
    # Learn from prior events so learned bridges are used when data exists
    resolved = project_path or getattr(context, "project_path", None)
    if resolved:
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
            world.learn(events)
        except Exception as exc:  # noqa: BLE001 - EventStore/world implementations are extension boundaries
            logger.debug("Failed to load events for world simulation learn: %s", exc, exc_info=True)

    current_state = world.observe()
    observed_event = bus.publish(
        type=EventType.WORLD_STATE_OBSERVED.value,
        payload=current_state.model_dump(mode="json"),
        caused_by=caused_by,
    )
    action = ObservabilityCollector.extract_objective_action(objective)
    sim_result = world.simulate(action, current_state)
    sim_payload = sim_result.model_dump(mode="json")
    sim_payload["action"] = action  # Store action for learner consumption
    blocked = sim_result.prediction.risk >= risk_threshold
    sim_event = bus.publish(
        type=EventType.WORLD_SIMULATION_RUN.value,
        payload=sim_payload,
        caused_by=observed_event.id,
        impact_score=sim_result.prediction.risk,
    )
    return (
        {
            "simulation": sim_payload,
            "prediction": sim_result.prediction.model_dump(mode="json"),
            "blocked": blocked,
        },
        sim_event.id,
        [observed_event, sim_event],
    )
