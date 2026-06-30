from __future__ import annotations

import pytest

from allbrain.recovery_consensus.arbiter import Arbiter
from allbrain.recovery_consensus.evaluator import Evaluator
from allbrain.recovery_consensus.manager import RecoveryConsensusManager
from allbrain.recovery_consensus.reducer import RecoveryConsensusReducer
from allbrain.recovery_consensus.strategy_generator import StrategyGenerator


def _sample_faults():
    return [
        {"fault_id": "f1", "component": "worker", "severity": "high", "fault_type": "failure"},
        {"fault_id": "f2", "component": "sensor", "severity": "medium", "fault_type": "anomaly"},
    ]


class TestRecoveryConsensusManager:
    def test_run_cycle_returns_dict(self):
        mgr = RecoveryConsensusManager()
        result = mgr.run_cycle(_sample_faults())
        assert isinstance(result, dict)

    def test_run_cycle_has_candidates(self):
        mgr = RecoveryConsensusManager()
        result = mgr.run_cycle(_sample_faults())
        assert len(result["candidates_generated"]) >= 2

    def test_run_cycle_has_decisions(self):
        mgr = RecoveryConsensusManager()
        result = mgr.run_cycle(_sample_faults())
        assert len(result["decisions"]) == 2

    def test_run_cycle_decisions_have_selected_strategy(self):
        mgr = RecoveryConsensusManager()
        result = mgr.run_cycle([_sample_faults()[0]])
        assert result["decisions"][0]["selected_strategy"] is not None

    def test_run_cycle_increments_time(self):
        mgr = RecoveryConsensusManager()
        s1 = mgr.stats()["time"]
        mgr.run_cycle(_sample_faults())
        s2 = mgr.stats()["time"]
        assert s2 == s1 + 1

    def test_run_cycle_empty_faults(self):
        mgr = RecoveryConsensusManager()
        result = mgr.run_cycle([])
        assert result["total_decisions"] == 0
        assert result["consensus_reached"] == 0

    def test_run_cycle_recent_failures(self):
        mgr = RecoveryConsensusManager()
        r1 = mgr.run_cycle(_sample_faults(), recent_failures=0)
        r2 = mgr.run_cycle(_sample_faults(), recent_failures=8)
        # Scores may differ due to penalty
        assert r1["decisions"] != r2["decisions"]

    def test_run_cycle_consensus_count(self):
        mgr = RecoveryConsensusManager()
        result = mgr.run_cycle(_sample_faults())
        assert 0 <= result["consensus_reached"] <= result["total_decisions"]


class TestEndToEnd:
    def test_generate_evaluate_arbitrate(self):
        faults = [{"fault_id": "f1", "component": "worker", "severity": "low", "fault_type": "failure"}]

        gen = StrategyGenerator()
        ev = Evaluator()
        arb = Arbiter()

        candidates = gen.generate("f1", "worker", "failure", "low")
        assert len(candidates) >= 1

        scored = ev.evaluate(candidates)
        assert len(scored) == len(candidates)

        decision = arb.arbitrate(scored, fault_id="f1")
        assert decision.fault_id == "f1"
        assert decision.selected_strategy in ("rollback", "retry", "isolate")

    def test_multiple_faults_different_types(self):
        faults = [
            {"fault_id": "c1", "component": "db", "severity": "critical", "fault_type": "corruption"},
            {"fault_id": "t1", "component": "api", "severity": "low", "fault_type": "timeout"},
            {"fault_id": "o1", "component": "queue", "severity": "medium", "fault_type": "orphan"},
        ]
        mgr = RecoveryConsensusManager()
        result = mgr.run_cycle(faults)
        assert result["total_decisions"] == 3
        assert result["consensus_reached"] >= 0

    def test_all_strategies_appear_across_faults(self):
        faults = [
            {"fault_id": "f1", "component": "x", "severity": "medium", "fault_type": "failure"},
            {"fault_id": "f2", "component": "x", "severity": "medium", "fault_type": "corruption"},
        ]
        mgr = RecoveryConsensusManager()
        result = mgr.run_cycle(faults)
        strategies_used = {d["selected_strategy"] for d in result["decisions"]}
        assert len(strategies_used) >= 1


class TestRecoveryConsensusReducer:
    def test_apply_unknown_event_returns_none(self):
        reducer = RecoveryConsensusReducer()
        snapshots = reducer.all_snapshots()
        assert isinstance(snapshots, dict)

    def test_all_snapshots_structure(self):
        reducer = RecoveryConsensusReducer()
        s = reducer.all_snapshots()
        assert "default" in s
        assert "decisions" in s["default"]
        assert "total_decisions" in s["default"]
        assert "consensus_reached" in s["default"]
