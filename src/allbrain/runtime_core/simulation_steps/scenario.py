"""Scenario generation step extracted from SimulationOrchestrator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.runtime_core.event_bus import RuntimeEventBus

if TYPE_CHECKING:
    from allbrain.domains.reasoning.scenarios import ScenarioEngine
    from allbrain.world import WorldModel

logger = logging.getLogger(__name__)


def execute(
    bus: RuntimeEventBus,
    action: str,
    caused_by: str,
    scenarios_limit: int,
    world: WorldModel,
    scenarios: ScenarioEngine,
) -> tuple[dict[str, Any], str, list[EventRead]]:
    """Run scenario generation step.

    Args:
        bus: Event bus for publishing events
        action: Action to analyze
        caused_by: Causal event ID
        scenarios_limit: Max scenarios to generate
        world: World model for state observation
        scenarios: Scenario generation engine

    Returns:
        Tuple of (scenario payload, last event ID, emitted events)
    """
    from allbrain.domains.reasoning.scenarios import SCENARIO_TEMPLATE_VERSION

    current_state = world.observe()
    observed_event = bus.publish(
        type=EventType.WORLD_STATE_OBSERVED.value,
        payload=current_state.model_dump(mode="json"),
        caused_by=caused_by,
    )
    analysis = scenarios.analyze(current_state, action, limit=scenarios_limit)
    analysis_payload = analysis.model_dump(mode="json")
    generated_event = bus.publish(
        type=EventType.SCENARIO_GENERATED.value,
        payload={
            "action": action,
            "templates": [item.scenario for item in analysis.results],
            "template_version": SCENARIO_TEMPLATE_VERSION,
            "analysis_id": analysis_payload["analysis_id"],
        },
        caused_by=observed_event.id,
    )
    evaluated_events: list[EventRead] = []
    for result in analysis.results:
        payload = {
            "analysis_id": analysis_payload["analysis_id"],
            "scenario": result.scenario,
            "prediction": result.prediction.model_dump(mode="json"),
            "confidence": result.confidence,
        }
        ev_event = bus.publish(
            type=EventType.SCENARIO_EVALUATED.value,
            payload=payload,
            caused_by=generated_event.id,
            impact_score=result.confidence,
        )
        evaluated_events.append(ev_event)
    rationale = (
        f"best={analysis.best_case.prediction.success_probability:.2f} "
        f"vs expected={analysis.expected_case.prediction.success_probability:.2f}, "
        f"spread={analysis.prediction_spread:.2f}"
    )
    recommendation_event = bus.publish(
        type=EventType.SCENARIO_RECOMMENDED.value,
        payload={
            "analysis_id": analysis_payload["analysis_id"],
            "best_case": analysis.best_case.model_dump(mode="json"),
            "expected_case": analysis.expected_case.model_dump(mode="json"),
            "rationale": rationale,
            "template_version": SCENARIO_TEMPLATE_VERSION,
        },
        caused_by=evaluated_events[-1].id,
        impact_score=analysis.prediction_spread,
    )
    summary = {
        "action": action,
        "analysis_id": analysis_payload["analysis_id"],
        "best_case": analysis.best_case.model_dump(mode="json"),
        "expected_case": analysis.expected_case.model_dump(mode="json"),
        "worst_case": analysis.worst_case.model_dump(mode="json"),
        "safest_case": analysis.safest_case.model_dump(mode="json"),
        "prediction_spread": analysis.prediction_spread,
        "risk_volatility": analysis.risk_volatility,
        "uncertainty": analysis.uncertainty,
        "confidence_total": analysis.confidence_total,
        "template_version": analysis.template_version,
        "rationale": rationale,
    }
    last_event_id = recommendation_event.id
    emitted_events: list[EventRead] = [observed_event, generated_event, *evaluated_events, recommendation_event]
    return summary, last_event_id, emitted_events
