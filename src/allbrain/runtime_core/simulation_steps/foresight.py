"""Foresight planning step extracted from SimulationOrchestrator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.runtime_core.event_bus import RuntimeEventBus

if TYPE_CHECKING:
    from allbrain.world import WorldModel

logger = logging.getLogger(__name__)


def execute(
    bus: RuntimeEventBus,
    action: str,
    caused_by: str,
    foresight_limit: int,
    max_horizon: int,
    world: WorldModel,
) -> tuple[dict[str, Any], str, list[EventRead]]:
    """Run foresight planning step.

    Args:
        bus: Event bus for publishing events
        action: Action to plan
        caused_by: Causal event ID
        foresight_limit: Max plans to generate
        max_horizon: Max planning horizon
        world: World model for state observation

    Returns:
        Tuple of (foresight payload, last event ID, emitted events)
    """
    from allbrain.domains.reasoning.foresight import FORESIGHT_TEMPLATE_VERSION, ForesightEngine

    current_state = world.observe()
    observed_event = bus.publish(
        type=EventType.WORLD_STATE_OBSERVED.value,
        payload=current_state.model_dump(mode="json"),
        caused_by=caused_by,
    )
    engine = ForesightEngine(max_horizon=max_horizon)
    analysis = engine.analyze(current_state, action, limit=foresight_limit)
    analysis_payload = analysis.model_dump(mode="json")
    generated_event = bus.publish(
        type=EventType.FORESIGHT_GENERATED.value,
        payload={
            "action": action,
            "plans_count": len(analysis.plans),
            "plan_ids": [f"plan_{idx}" for idx in range(len(analysis.plans))],
            "template_version": FORESIGHT_TEMPLATE_VERSION,
            "analysis_id": analysis_payload["analysis_id"],
        },
        caused_by=observed_event.id,
    )
    evaluated_events: list[EventRead] = []
    for idx, plan in enumerate(analysis.plans):
        plan_payload = plan.model_dump(mode="json")
        plan_payload["analysis_id"] = analysis_payload["analysis_id"]
        plan_payload["plan_id"] = f"plan_{idx}"
        ev_event = bus.publish(
            type=EventType.FORESIGHT_EVALUATED.value,
            payload=plan_payload,
            caused_by=generated_event.id,
            impact_score=plan.predicted_success,
        )
        evaluated_events.append(ev_event)
    rationale = (
        f"best={analysis.best_plan.predicted_success:.2f} "
        f"horizon={analysis.expected_plan.horizon} "
        f"spread={analysis.plan_spread:.2f}"
    )
    recommendation_event = bus.publish(
        type=EventType.FORESIGHT_RECOMMENDED.value,
        payload={
            "analysis_id": analysis_payload["analysis_id"],
            "best_plan": analysis.best_plan.model_dump(mode="json"),
            "expected_plan": analysis.expected_plan.model_dump(mode="json"),
            "rationale": rationale,
            "template_version": FORESIGHT_TEMPLATE_VERSION,
        },
        caused_by=evaluated_events[-1].id if evaluated_events else generated_event.id,
        impact_score=analysis.plan_spread,
    )
    summary = {
        "action": action,
        "analysis_id": analysis_payload["analysis_id"],
        "best_plan": analysis.best_plan.model_dump(mode="json"),
        "safest_plan": analysis.safest_plan.model_dump(mode="json"),
        "fastest_plan": analysis.fastest_plan.model_dump(mode="json"),
        "expected_plan": analysis.expected_plan.model_dump(mode="json"),
        "plan_spread": analysis.plan_spread,
        "strategy_uncertainty": analysis.strategy_uncertainty,
        "horizon_risk": analysis.horizon_risk,
        "template_version": analysis.template_version,
        "rationale": rationale,
    }
    last_event_id = recommendation_event.id
    emitted_events: list[EventRead] = [observed_event, generated_event, *evaluated_events, recommendation_event]
    return summary, last_event_id, emitted_events
