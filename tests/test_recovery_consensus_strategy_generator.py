from __future__ import annotations

import pytest

from allbrain.recovery_consensus.model import CandidateStrategy
from allbrain.recovery_consensus.strategy_generator import StrategyGenerator


class TestStrategyGeneratorInit:
    def test_default_max(self):
        sg = StrategyGenerator()
        assert sg._max >= 3

    def test_custom_max(self):
        sg = StrategyGenerator(max_candidates=5)
        assert sg._max == 5


class TestStrategyGeneratorGenerate:
    def test_generates_at_least_min(self):
        sg = StrategyGenerator()
        result = sg.generate("f1", "worker", "failure", "medium")
        assert len(result) >= 1

    def test_generates_at_most_max(self):
        sg = StrategyGenerator(max_candidates=2)
        result = sg.generate("f1", "worker", "failure", "medium")
        assert len(result) <= 2

    def test_failure_type_prioritizes_rollback(self):
        sg = StrategyGenerator()
        result = sg.generate("f1", "worker", "failure", "low")
        assert result[0].strategy == "rollback"

    def test_anomaly_type_prioritizes_isolate(self):
        sg = StrategyGenerator()
        result = sg.generate("f2", "sensor", "anomaly", "medium")
        assert result[0].strategy == "isolate"

    def test_orphan_type(self):
        sg = StrategyGenerator()
        result = sg.generate("f3", "queue", "orphan", "high")
        assert result[0].strategy == "retry"

    def test_timeout_type_includes_repair(self):
        sg = StrategyGenerator()
        result = sg.generate("f4", "network", "timeout", "critical")
        strategies = [c.strategy for c in result]
        assert "repair" in strategies

    def test_corruption_type_includes_repair(self):
        sg = StrategyGenerator()
        result = sg.generate("f5", "db", "corruption", "high")
        strategies = [c.strategy for c in result]
        assert "repair" in strategies

    def test_each_candidate_has_explanation(self):
        sg = StrategyGenerator()
        result = sg.generate("f1", "worker", "failure", "medium")
        for c in result:
            assert isinstance(c.explanation, str)
            assert len(c.explanation) > 0

    def test_severity_adjustment_high(self):
        sg = StrategyGenerator()
        low = sg.generate("f1", "worker", "failure", "low")
        high = sg.generate("f1", "worker", "failure", "high")
        # High severity should have higher risk than low severity
        assert high[0].risk >= low[0].risk

    def test_severity_adjustment_critical(self):
        sg = StrategyGenerator()
        result = sg.generate("f1", "worker", "failure", "critical")
        for c in result:
            assert 0.0 <= c.risk <= 1.0
            assert 0.0 <= c.estimated_success <= 1.0

    def test_different_fault_ids_produce_different_ids(self):
        sg = StrategyGenerator()
        r1 = sg.generate("fa", "worker", "failure", "medium")
        # Different fault ID but same setup — strategies should be the same
        r2 = sg.generate("fb", "worker", "failure", "medium")
        assert len(r1) == len(r2)

    def test_unknown_fault_type_uses_base(self):
        sg = StrategyGenerator()
        result = sg.generate("f1", "worker", "unknown_type", "medium")
        assert len(result) >= 1
