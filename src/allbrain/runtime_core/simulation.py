"""Simulation orchestration extracted from SystemDecisionPipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.runtime_core.contracts import RuntimeContext
from allbrain.runtime_core.event_bus import RuntimeEventBus
from allbrain.runtime_core.observability import ObservabilityCollector

if TYPE_CHECKING:
    from allbrain.domains.reasoning.counterfactual import CounterfactualEngine
    from allbrain.domains.reasoning.foresight import ForesightEngine
    from allbrain.domains.reasoning.scenarios import ScenarioEngine
    from allbrain.world import WorldModel

logger = logging.getLogger(__name__)


class SimulationOrchestrator:
    """Orchestrates world simulation, counterfactual, scenario, and foresight analysis."""

    def __init__(
        self,
        world: WorldModel,
        counterfactual: CounterfactualEngine,
        scenarios: ScenarioEngine,
        foresight: ForesightEngine,
        uuid7_generator: Any,
    ) -> None:
        """Initialize simulation orchestrator.

        Args:
            world: World model for state observation and simulation
            counterfactual: Counterfactual analysis engine
            scenarios: Scenario generation engine
            foresight: Foresight planning engine
            uuid7_generator: UUID7 generator function
        """
        self.world = world
        self.counterfactual = counterfactual
        self.scenarios = scenarios
        self.foresight = foresight
        self._uuid7 = uuid7_generator

    def simulation_step(
        self,
        bus: RuntimeEventBus,
        context: RuntimeContext,
        project_path: str | None,
        objective: dict[str, Any],
        caused_by: str,
        risk_threshold: float,
        limit: int = 500,
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

        Returns:
            Tuple of (simulation payload, last event ID, emitted events)
        """
        # Learn from prior events so learned bridges are used when data exists
        resolved = project_path or getattr(context, "project_path", None)
        if resolved:
            try:
                events = context.repository.list_events(project_path=resolved, limit=limit)
                self.world.learn(events)
            except Exception as exc:
                logger.debug("Failed to load events for world simulation learn: %s", exc, exc_info=True)

        current_state = self.world.observe()
        observed_event = bus.publish(
            type=EventType.WORLD_STATE_OBSERVED.value,
            payload=current_state.model_dump(mode="json"),
            caused_by=caused_by,
        )
        action = ObservabilityCollector.extract_objective_action(objective)
        sim_result = self.world.simulate(action, current_state)
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

    def counterfactual_step(
        self,
        bus: RuntimeEventBus,
        action: str,
        caused_by: str,
        regret_threshold: float,
        counterfactual_limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Run counterfactual analysis step.

        Args:
            bus: Event bus for publishing events
            action: Action to analyze
            caused_by: Causal event ID
            regret_threshold: Regret threshold for recommendations
            counterfactual_limit: Max counterfactuals to generate

        Returns:
            Tuple of (counterfactual payload, last event ID, emitted events)
        """
        from allbrain.domains.reasoning.counterfactual import recommendation_severity

        current_state = self.world.observe()
        observed_event = bus.publish(
            type=EventType.WORLD_STATE_OBSERVED.value,
            payload=current_state.model_dump(mode="json"),
            caused_by=caused_by,
        )
        generated_payload: dict[str, Any] = {"action": action, "alternatives": []}
        unknown = not self.counterfactual.generator.generate(action)
        if unknown:
            generated_payload["reason"] = "unknown_action"
        generated_event = bus.publish(
            type=EventType.COUNTERFACTUAL_GENERATED.value,
            payload=generated_payload,
            caused_by=observed_event.id,
        )
        alternatives = self.counterfactual.generator.generate(action)[:counterfactual_limit]
        results_payloads: list[dict[str, Any]] = []
        evaluated_events: list[EventRead] = []
        for alternative in alternatives:
            result = self.counterfactual.evaluator.compare(current_state, action, alternative)
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

    def foresight_step(
        self,
        bus: RuntimeEventBus,
        action: str,
        caused_by: str,
        foresight_limit: int,
        max_horizon: int,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Run foresight planning step.

        Args:
            bus: Event bus for publishing events
            action: Action to plan
            caused_by: Causal event ID
            foresight_limit: Max plans to generate
            max_horizon: Max planning horizon

        Returns:
            Tuple of (foresight payload, last event ID, emitted events)
        """
        from allbrain.domains.reasoning.foresight import FORESIGHT_TEMPLATE_VERSION, ForesightEngine

        current_state = self.world.observe()
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

    def scenario_step(
        self,
        bus: RuntimeEventBus,
        action: str,
        caused_by: str,
        scenarios_limit: int,
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        """Run scenario generation step.

        Args:
            bus: Event bus for publishing events
            action: Action to analyze
            caused_by: Causal event ID
            scenarios_limit: Max scenarios to generate

        Returns:
            Tuple of (scenario payload, last event ID, emitted events)
        """
        from allbrain.domains.reasoning.scenarios import SCENARIO_TEMPLATE_VERSION

        current_state = self.world.observe()
        observed_event = bus.publish(
            type=EventType.WORLD_STATE_OBSERVED.value,
            payload=current_state.model_dump(mode="json"),
            caused_by=caused_by,
        )
        analysis = self.scenarios.analyze(current_state, action, limit=scenarios_limit)
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

