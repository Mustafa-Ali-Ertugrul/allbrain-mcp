from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.domains.memory.runtime_core.contracts import RuntimeContext
from allbrain.domains.memory.runtime_core.event_bus import RuntimeEventBus
from allbrain.domains.memory.runtime_core.state import RuntimeStateMachine, RuntimeStatus


@dataclass(frozen=True)
class PipelineRunOptions:
    execute_mode: str = "event_only"
    project_path: str | None = None
    limit: int = 5000
    simulate_before_execute: bool = False
    risk_threshold: float = 0.7
    enable_counterfactual: bool = False
    counterfactual_limit: int = 3
    regret_threshold: float = 0.20
    enable_scenarios: bool = False
    scenarios_limit: int = 4
    scenario_recommendation_threshold: float = 0.50
    enable_foresight: bool = False
    foresight_limit: int = 5
    max_horizon: int = 5
    enable_meta_reasoning: bool = False
    enable_uncertainty: bool = False
    enable_information_seeking: bool = False

    def validate(self) -> None:
        if self.execute_mode not in {"event_only", "mock_runtime", "queued_runtime"}:
            raise ValueError("execute_mode must be 'event_only', 'mock_runtime', or 'queued_runtime'")
        for name, value in (
            ("risk_threshold", self.risk_threshold),
            ("regret_threshold", self.regret_threshold),
            ("scenario_recommendation_threshold", self.scenario_recommendation_threshold),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0")
        for name, value in (
            ("counterfactual_limit", self.counterfactual_limit),
            ("scenarios_limit", self.scenarios_limit),
            ("foresight_limit", self.foresight_limit),
            ("max_horizon", self.max_horizon),
        ):
            if value < 1:
                raise ValueError(f"{name} must be >= 1")


@dataclass
class PipelineRunState:
    context: RuntimeContext
    objective: dict[str, Any]
    options: PipelineRunOptions
    run_id: str
    bus: RuntimeEventBus
    machine: RuntimeStateMachine
    emitted: list[EventRead] = field(default_factory=list)
    last_event_id: str | None = None
    status: str = "RUNNING"
    governance: dict[str, Any] = field(default_factory=dict)
    economic: dict[str, Any] = field(default_factory=dict)
    strategic_plan: dict[str, Any] = field(default_factory=dict)
    decomposition: dict[str, Any] = field(default_factory=dict)
    execution_plan: dict[str, Any] = field(default_factory=dict)
    arbitration: dict[str, Any] = field(default_factory=dict)
    final_decision: dict[str, Any] = field(default_factory=dict)
    scheduler: dict[str, Any] | None = None
    feedback: dict[str, Any] | None = None
    learning: dict[str, Any] | None = None
    world_simulation: dict[str, Any] | None = None
    world_payload: dict[str, Any] | None = field(default=None, repr=False)
    counterfactual: dict[str, Any] | None = None
    scenarios: dict[str, Any] | None = None
    foresight: dict[str, Any] | None = None
    meta_reasoning: dict[str, Any] | None = None
    uncertainty: dict[str, Any] | None = None
    information_seeking: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        context: RuntimeContext,
        objective: dict[str, Any],
        options: PipelineRunOptions,
        uuid7_generator: Callable[[], Any],
    ) -> PipelineRunState:
        run_id = str(uuid7_generator())
        return cls(
            context=context,
            objective=objective,
            options=options,
            run_id=run_id,
            bus=RuntimeEventBus(context, project_path=options.project_path),
            machine=RuntimeStateMachine(run_id),
        )

    def publish(self, type: str, payload: dict[str, Any], caused_by: str | None = None, **extra: Any) -> EventRead:
        event = self.bus.publish(
            type=type,
            payload={"run_id": self.run_id, **payload},
            caused_by=caused_by,
            **extra,
        )
        self.emitted.append(event)
        self.last_event_id = event.id
        return event

    def transition(self, target: RuntimeStatus, reason: str) -> str:
        payload = self.machine.transition(target, reason=reason)
        return self.publish(
            EventType.PIPELINE_STATE_CHANGED.value,
            payload,
            caused_by=self.last_event_id,
        ).id

    def result(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "objective": self.objective,
            "governance": self.governance,
            "economic": self.economic,
            "strategic_plan": self.strategic_plan,
            "decomposition": self.decomposition,
            "execution_plan": self.execution_plan,
            "arbitration": self.arbitration,
            "final_decision": self.final_decision,
            "scheduler": self.scheduler,
            "feedback": self.feedback,
            "learning": self.learning,
            "world_simulation": self.world_simulation,
            "counterfactual": self.counterfactual,
            "scenarios": self.scenarios,
            "foresight": self.foresight,
            "meta_reasoning": self.meta_reasoning,
            "uncertainty": self.uncertainty,
            "information_seeking": self.information_seeking,
            "events": [event.model_dump(mode="json") for event in self.emitted],
        }
