from __future__ import annotations

from types import SimpleNamespace
import pytest

from allbrain.events.schemas import EventType
from allbrain.recovery_consensus.evaluator import Evaluator
from allbrain.recovery_consensus.events import (
    make_consensus_reached_payload,
    make_strategies_generated_payload,
    make_strategy_evaluated_payload,
    make_strategy_rejected_payload,
    make_strategy_selected_payload,
    validate_consensus_reached,
    validate_strategies_generated,
    validate_strategy_evaluated,
    validate_strategy_rejected,
    validate_strategy_selected,
)
from allbrain.recovery_consensus.manager import RecoveryConsensusManager
from allbrain.recovery_consensus.reducer import RecoveryConsensusReducer
from allbrain.recovery_consensus.strategy_generator import StrategyGenerator


class FakeEvent(SimpleNamespace):
    id: str
    type: str
    payload: dict | None
    created_at: str | None = None
    caused_by: str | None = None


def test_strategy_generator_fault_types_and_severities():
    generator = StrategyGenerator(max_candidates=5)

    for ft in ["failure", "anomaly", "orphan", "corruption", "timeout", "unknown"]:
        candidates = generator.generate(fault_id="f_1", component="worker", fault_type=ft, severity="critical")
        assert len(candidates) > 0
        assert all(c.fault_id == "f_1" for c in candidates)
        assert all(0.0 <= c.risk <= 1.0 for c in candidates)
        assert all(0.0 <= c.estimated_success <= 1.0 for c in candidates)

    gen_id = StrategyGenerator._stable_generation_id("f_1", 3)
    assert len(gen_id) == 12


def test_recovery_consensus_manager_run_cycle_and_stats():
    manager = RecoveryConsensusManager(bias_weight=0.1)

    faults = [
        {"fault_id": "f_10", "component": "db", "fault_type": "corruption", "severity": "high"},
        {"fault_id": "f_20", "component": "cache", "fault_type": "timeout", "severity": "low"},
    ]

    res = manager.run_cycle(faults, recent_failures=1)
    assert "candidates_generated" in res
    assert "decisions" in res
    assert res["total_decisions"] == 2
    assert manager.stats()["time"] == 1


def test_recovery_consensus_reducer_and_events():
    reducer = RecoveryConsensusReducer()

    p_gen = make_strategies_generated_payload(fault_id="f_1", candidate_count=1, strategies=["rollback"])
    p_eval = make_strategy_evaluated_payload(
        fault_id="f_1", strategy="rollback", score=0.9, risk=0.1, estimated_success=0.9, confidence=0.8
    )
    p_reach = make_consensus_reached_payload(
        decision_id="dec_1", fault_id="f_1", selected_strategy="rollback", consensus_score=0.9, candidate_count=1
    )
    p_rej = make_strategy_rejected_payload(decision_id="dec_2", fault_id="f_1", strategy="rollback", score=0.2, reason="too risky")
    p_sel = make_strategy_selected_payload(decision_id="dec_3", fault_id="f_1", selected_strategy="retry", consensus_score=0.85, reason="best fit")

    reducer.apply(FakeEvent(id="e1", type=EventType.RECOVERY_STRATEGIES_GENERATED.value, payload=p_gen))
    reducer.apply(FakeEvent(id="e1", type=EventType.RECOVERY_STRATEGIES_GENERATED.value, payload=p_gen))  # duplicate
    reducer.apply(FakeEvent(id="e2", type=EventType.RECOVERY_STRATEGY_EVALUATED.value, payload=p_eval))
    reducer.apply(FakeEvent(id="e3", type=EventType.RECOVERY_CONSENSUS_REACHED.value, payload=p_reach))
    reducer.apply(FakeEvent(id="e4", type=EventType.RECOVERY_STRATEGY_REJECTED.value, payload=p_rej))
    reducer.apply(FakeEvent(id="e5", type=EventType.RECOVERY_STRATEGY_SELECTED.value, payload=p_sel))

    # Invalid events
    reducer.apply(FakeEvent(id="e6", type=EventType.RECOVERY_CONSENSUS_REACHED.value, payload={"bad": 1}))
    reducer.apply(FakeEvent(id="e7", type=EventType.RECOVERY_STRATEGY_REJECTED.value, payload={"bad": 1}))
    reducer.apply(FakeEvent(id="e8", type=EventType.RECOVERY_STRATEGY_SELECTED.value, payload={"bad": 1}))
    reducer.apply(FakeEvent(id="e9", type="other", payload=None))

    snap = reducer.snapshot()
    assert snap["total_decisions"] == 2
    assert snap["consensus_reached"] == 1
    assert snap["rejected_count"] == 1

    all_snaps = reducer.all_snapshots()
    assert "default" in all_snaps


def test_recovery_consensus_all_validators_and_evaluator():
    with pytest.raises(ValueError):
        validate_strategies_generated({"fault_id": 123})
    with pytest.raises(ValueError):
        validate_strategies_generated({"fault_id": "f", "candidate_count": "bad"})
    with pytest.raises(ValueError):
        validate_strategies_generated({"fault_id": "f", "candidate_count": 1, "strategies": "bad"})

    with pytest.raises(ValueError):
        validate_strategy_evaluated({"fault_id": "f1", "strategy": "invalid_strat"})
    with pytest.raises(ValueError):
        validate_strategy_evaluated({"fault_id": 123})

    with pytest.raises(ValueError):
        validate_consensus_reached({"decision_id": 123})

    with pytest.raises(ValueError):
        validate_strategy_rejected({"decision_id": 123})

    with pytest.raises(ValueError):
        validate_strategy_selected({"decision_id": 123})

    evaluator = Evaluator()
    generator = StrategyGenerator()
    candidates = generator.generate("f1", "comp", "timeout", "low")
    scored = evaluator.evaluate(candidates, recent_failures=5, fault_type="timeout")
    assert len(scored) == len(candidates)
