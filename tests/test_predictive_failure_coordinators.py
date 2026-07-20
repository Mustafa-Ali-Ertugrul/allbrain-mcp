from __future__ import annotations

from types import SimpleNamespace

from allbrain.domains.analysis.predictive_failure.learning_repair import LearningRepairCoordinator
from allbrain.domains.analysis.predictive_failure.model import MitigationPlan
from allbrain.domains.analysis.predictive_failure.strategy_selection import StrategySelectionCoordinator
from allbrain.events.schemas import EventType


class Planner:
    def __init__(self, mitigation):
        self.mitigation = mitigation

    def plan(self, _prediction):
        return self.mitigation


def mitigation(strategy: str = "restart") -> MitigationPlan:
    return MitigationPlan(
        plan_id="plan-1",
        fault_id="fault-1",
        fault_type="latency",
        strategy=strategy,
        urgency=0.5,
        expected_risk_reduction=0.25,
    )


def test_strategy_selection_returns_none_when_planner_has_no_mitigation() -> None:
    owner = SimpleNamespace(_planner=Planner(None))
    events: list[dict] = []

    selected, candidates = StrategySelectionCoordinator(owner).select(
        "fault-1",
        "latency",
        SimpleNamespace(),
        (),
        events,
    )

    assert selected is None
    assert candidates == []
    assert events == []


def test_strategy_selection_emits_default_plan_without_optimizer() -> None:
    plan = mitigation()
    owner = SimpleNamespace(_planner=Planner(plan), _strategy_optimizer=None, _learning_engine=None)
    events: list[dict] = []

    selected, candidates = StrategySelectionCoordinator(owner).select(
        "fault-1",
        "latency",
        SimpleNamespace(),
        ("cpu",),
        events,
    )

    assert selected is plan
    assert candidates == []
    assert events == [
        {
            "event_type": EventType.PROACTIVE_MITIGATION_PLANNED.value,
            "plan_id": "plan-1",
            "fault_id": "fault-1",
            "fault_type": "latency",
            "strategy": "restart",
            "urgency": 0.5,
            "expected_risk_reduction": 0.25,
        }
    ]


def test_replace_mitigation_uses_selected_strategy() -> None:
    prediction = SimpleNamespace(fault_id="fault-1", fault_type="latency", probability=0.8)

    replacement = StrategySelectionCoordinator._replace_mitigation(prediction, "scale_out")

    assert replacement.fault_id == "fault-1"
    assert replacement.fault_type == "latency"
    assert replacement.strategy == "scale_out"
    assert 0.0 <= replacement.expected_risk_reduction <= 1.0


def test_learning_repair_returns_empty_when_required_services_missing() -> None:
    owner = SimpleNamespace(_outcome_tracker=None, _learning_engine=None)
    events: list[dict] = []

    stats, stability = LearningRepairCoordinator(owner).run(
        "fault-1",
        "latency",
        mitigation(),
        SimpleNamespace(success=True),
        0.9,
        ("cpu",),
        events,
        now=1.0,
    )

    assert stats is None
    assert stability is None
    assert events == []


def test_validated_effectiveness_records_capped_simulation_weight() -> None:
    class Validator:
        simulation_weight = 0.8
        real_weight = 0.2

        def call_real_provider(self, _strategy, _pre_risk, _urgency):
            return None

        def compute_combined_effectiveness(self, *, sim_effectiveness, real_effectiveness):
            assert sim_effectiveness == 0.5
            assert real_effectiveness is None
            return 0.5, True

        def is_real_provider_set(self):
            return False

    owner = SimpleNamespace(_outcome_validator=Validator())
    events: list[dict] = []

    effectiveness = LearningRepairCoordinator(owner)._validated_effectiveness(
        "latency",
        mitigation(),
        SimpleNamespace(pre_risk=1.0, post_risk=0.5),
        events,
    )

    assert effectiveness == 0.5
    assert events == [
        {
            "event_type": EventType.SIMULATION_WEIGHT_CAPPED.value,
            "fault_type": "latency",
            "simulation_weight": 0.8,
            "real_weight": 0.2,
            "is_real_provider_set": False,
        }
    ]
