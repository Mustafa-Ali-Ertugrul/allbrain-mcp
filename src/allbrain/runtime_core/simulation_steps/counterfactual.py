"""Counterfactual analysis step extracted from SimulationOrchestrator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.runtime_core.event_bus import RuntimeEventBus

if TYPE_CHECKING:
    from allbrain.domains.reasoning.counterfactual import CounterfactualEngine
    from allbrain.world import WorldModel

logger = logging.getLogger(__name__)


def execute(
    bus: RuntimeEventBus,
    action: str,
    caused_by: str,
    regret_threshold: float,
    counterfactual_limit: int,
    world: WorldModel,
    counterfactual: CounterfactualEngine,
) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
    """Run counterfactual analysis step.

    Args:
        bus: Event bus for publishing events
        action: Action to analyze
        caused_by: Causal event ID
        regret_threshold: Regret threshold for recommendations
        counterfactual_limit: Max counterfactuals to generate
        world: World model for state observation
        counterfactual: Counterfactual analysis engine

    Returns:
        Tuple of (counterfactual payload, last event ID, emitted events)
    """
    from allbrain.domains.reasoning.counterfactual import recommendation_severity

    current_state = world.observe()
    observed_event = bus.publish(
        type=EventType.WORLD_STATE_OBSERVED.value,
        payload=current_state.model_dump(mode="json"),
        caused_by=caused_by,
    )
    generated_payload: dict[str, Any] = {"action": action, "alternatives": []}
    unknown = not counterfactual.generator.generate(action)
    if unknown:
        generated_payload["reason"] = "unknown_action"
    generated_event = bus.publish(
        type=EventType.COUNTERFACTUAL_GENERATED.value,
        payload=generated_payload,
        caused_by=observed_event.id,
    )
    alternatives = counterfactual.generator.generate(action)[:counterfactual_limit]
    results_payloads: list[dict[str, Any]] = []
    evaluated_events: list[EventRead] = []
    for alternative in alternatives:
        result = counterfactual.evaluator.compare(current_state, action, alternative)
        ev_event = bus.publish(
            type=EventType.COUNTERFACTUAL_EVALUATED.value,
            payload=result.model_dump(mode="json"),
            caused_by=generated_event.id,
        )
        results_payloads.append(result.model_dump(mode="json"))
        evaluated_events.append(ev_event)
    best_payload: dict[str, Any] | None = None
    recommendation_event: EventRead | None = None
    if results_payloads:
        best_payload = max(results_payloads, key=lambda item: item["improvement"])
        if best_payload["improvement"] >= regret_threshold:
            severity = recommendation_severity(best_payload["improvement"])
            last_id = evaluated_events[-1].id if evaluated_events else generated_event.id
            recommendation_event = bus.publish(
                type=EventType.COUNTERFACTUAL_RECOMMENDATION.value,
                payload={"best": best_payload, "threshold": regret_threshold, "severity": severity},
                caused_by=last_id,
                impact_score=best_payload["improvement"],
            )
    summary = {
        "action": action,
        "alternatives": alternatives,
        "unknown_action": unknown,
        "results": results_payloads,
        "best": best_payload,
        "decision_regret": best_payload["regret"] if best_payload else 0.0,
        "recommendation_emitted": recommendation_event is not None,
    }
    last_event_id = (recommendation_event or (evaluated_events[-1] if evaluated_events else generated_event)).id
    emitted_events: list[EventRead] = [observed_event, generated_event, *evaluated_events]
    if recommendation_event is not None:
        emitted_events.append(recommendation_event)
    return summary, last_event_id, emitted_events

