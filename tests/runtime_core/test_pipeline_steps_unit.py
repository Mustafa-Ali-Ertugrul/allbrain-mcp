from __future__ import annotations

from types import SimpleNamespace

from allbrain.domains.memory.runtime_core.pipeline_steps.decision import DecisionPreparationStep
from allbrain.domains.memory.runtime_core.pipeline_steps.learning import LearningCompletionStep
from allbrain.domains.memory.runtime_core.pipeline_steps.reasoning import ReasoningStep
from allbrain.domains.memory.runtime_core.state import RuntimeStatus
from allbrain.events import EventType


class FakeState(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transitions = []
        self.published = []

    def transition(self, target: RuntimeStatus, reason: str) -> str:
        self.transitions.append((target, reason))
        self.last_event_id = f"transition::{reason}"
        return self.last_event_id

    def publish(self, type: str, payload: dict, caused_by: str | None = None, **extra):
        event = SimpleNamespace(id=f"event::{type}", type=type, payload=payload, caused_by=caused_by, extra=extra)
        self.published.append(event)
        self.last_event_id = event.id
        return event


def test_record_final_decision_accepts_ready_pipeline() -> None:
    state = FakeState(
        governance={"governance_decision": {"decision": "approve", "confidence": 0.9}},
        economic={"decision": "proceed", "confidence": 0.8},
        arbitration={"action": "accept", "confidence": 0.7},
        final_decision={},
        last_event_id="previous",
        status="RUNNING",
    )

    assert DecisionPreparationStep._record_final_decision(state) is True

    assert state.final_decision == {"action": "accept", "reason": "pipeline_ready", "confidence": 0.8}
    assert state.transitions[-1] == (RuntimeStatus.DECISION, "final_decision")
    assert state.published[-1].type == EventType.FINAL_DECISION_RECORDED.value


def test_record_final_decision_blocks_on_governance_rejection() -> None:
    state = FakeState(
        governance={"governance_decision": {"decision": "reject_expansion", "confidence": 0.4}},
        economic={"decision": "proceed", "confidence": 0.8},
        arbitration={"action": "accept", "confidence": 0.7},
        final_decision={},
        last_event_id="previous",
        status="RUNNING",
    )

    assert DecisionPreparationStep._record_final_decision(state) is False

    assert state.status == "BLOCKED"
    assert state.final_decision == {"action": "reject", "reason": "reject_expansion", "confidence": 0.4}
    assert state.transitions[-1] == (RuntimeStatus.BLOCKED, "reject_expansion")
    assert state.published[-1].type == EventType.PIPELINE_RUN_COMPLETED.value


def test_learning_prediction_includes_optional_reasoning_layers() -> None:
    state = SimpleNamespace(
        execution_plan={"execution_plan_id": "plan-1", "predicted_cost": 12.0},
        counterfactual={"best": {"alternative_prediction": {"success_probability": 0.9}, "regret": 0.2}},
        scenarios={"prediction_spread": 0.3, "risk_volatility": 0.4, "uncertainty": 0.5},
        foresight={"expected_plan": {"horizon": 4}, "strategy_uncertainty": 0.6, "horizon_risk": 0.7},
    )

    prediction = LearningCompletionStep._learning_prediction(state)

    assert prediction["best_alternative"] == 0.9
    assert prediction["regret"] == 0.2
    assert prediction["prediction_spread"] == 0.3
    assert prediction["future_horizon"] == 4
    assert prediction["horizon_risk"] == 0.7


def test_completed_payload_omits_absent_optional_layers() -> None:
    state = SimpleNamespace(
        final_decision={"action": "accept"},
        world_simulation=None,
        counterfactual={"best": "candidate"},
        scenarios=None,
        foresight=None,
        meta_reasoning=None,
        uncertainty=None,
        information_seeking=None,
        learning={"error_delta": 0.1},
    )

    payload = LearningCompletionStep._completed_payload(state)

    assert payload == {
        "status": "COMPLETED",
        "final_decision": {"action": "accept"},
        "counterfactual": {"best": "candidate"},
        "learning": {"error_delta": 0.1},
    }


def test_simulate_world_blocks_high_risk_payload() -> None:
    payload = {"blocked": True, "simulation": {"risk": 0.99}, "prediction": {"success_probability": 0.1}}
    state = FakeState(
        options=SimpleNamespace(simulate_before_execute=True, project_path=None, risk_threshold=0.7, limit=10),
        bus=object(),
        context=object(),
        objective={"goal": "risky"},
        last_event_id="previous",
        final_decision={"action": "accept"},
        execution_plan={},
        emitted=[],
        status="RUNNING",
    )
    services = SimpleNamespace(
        simulation=SimpleNamespace(
            simulation_step=lambda *_args: (payload, "sim-event", [SimpleNamespace(id="sim-event")])
        )
    )

    assert ReasoningStep._simulate_world(state, services) is False

    assert state.status == "BLOCKED"
    assert state.world_simulation == {"risk": 0.99}
    assert state.transitions[-1] == (RuntimeStatus.BLOCKED, "world_simulation_high_risk")
    assert state.published[-1].type == EventType.PIPELINE_RUN_COMPLETED.value
