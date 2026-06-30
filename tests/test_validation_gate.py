from __future__ import annotations

import pytest

from allbrain.mitigation_learning.model import StrategyStats
from allbrain.self_repair.model import MIN_STABILITY_THRESHOLD
from allbrain.self_repair.validation_gate import ValidationGate


def _make_stats(ft, sig, strat, uses=10, succ=8, eff=0.7):
    return StrategyStats(
        fault_type=ft,
        signal_type=sig,
        strategy=strat,
        total_uses=uses,
        successes=succ,
        failures=uses - succ,
        avg_effectiveness=eff,
        success_rate=succ / max(uses, 1),
    )


class TestValidationGate:
    def setup_method(self):
        self.gate = ValidationGate()

    def test_accepts_high_success_rate(self):
        stats = {
            ("t", "s", "A"): _make_stats("t", "s", "A", uses=10, succ=9, eff=0.9),
        }
        result = self.gate.validate(fault_type="t", version=2, all_stats=stats)
        assert result.accepted

    def test_rejects_low_success_rate(self):
        stats = {
            ("t", "s", "A"): _make_stats("t", "s", "A", uses=10, succ=0, eff=0.01),
        }
        result = self.gate.validate(
            fault_type="t",
            version=2,
            all_stats=stats,
            drift_events_recent=3,
            safety_violations=2,
        )
        assert not result.accepted
        assert len(result.failure_reasons) > 0

    def test_accepts_with_no_history(self):
        result = self.gate.validate(fault_type="t", version=1, all_stats={}, drift_events_recent=0)
        assert not result.accepted
        assert result.stability_score == 0.0

    def test_stability_formula_single_strategy(self):
        stats = {
            ("t", "s", "A"): _make_stats("t", "s", "A", uses=10, succ=8, eff=0.7),
        }
        report = self.gate.compute_stability(fault_type="t", version=2, all_stats=stats)
        assert report.stability_score > 0
        assert report.stability_score <= 1.0

    def test_rejection_provides_reasons(self):
        stats = {
            ("t", "s", "A"): _make_stats("t", "s", "A", uses=10, succ=0, eff=0.0),
        }
        result = self.gate.validate(
            fault_type="t",
            version=2,
            all_stats=stats,
            drift_events_recent=5,
            safety_violations=3,
        )
        assert not result.accepted
        assert any("low_success_rate" in r for r in result.failure_reasons)

    def test_drift_events_penalize(self):
        stats = {
            ("t", "s", "A"): _make_stats("t", "s", "A", uses=10, succ=8, eff=0.7),
        }
        report_no_drift = self.gate.compute_stability(
            fault_type="t",
            version=2,
            all_stats=stats,
            drift_events_recent=0,
        )
        report_with_drift = self.gate.compute_stability(
            fault_type="t",
            version=2,
            all_stats=stats,
            drift_events_recent=3,
        )
        assert report_with_drift.stability_score < report_no_drift.stability_score

    def test_safety_violations_penalize(self):
        stats = {
            ("t", "s", "A"): _make_stats("t", "s", "A", uses=10, succ=8, eff=0.7),
        }
        report_clean = self.gate.compute_stability(
            fault_type="t",
            version=2,
            all_stats=stats,
            safety_violations=0,
        )
        report_violated = self.gate.compute_stability(
            fault_type="t",
            version=2,
            all_stats=stats,
            safety_violations=5,
        )
        assert report_violated.stability_score < report_clean.stability_score

    def test_is_stable_property(self):
        stats = {
            ("t", "s", "A"): _make_stats("t", "s", "A", uses=10, succ=9, eff=0.9),
        }
        report = self.gate.compute_stability(fault_type="t", version=2, all_stats=stats)
        assert report.is_stable == (report.stability_score >= MIN_STABILITY_THRESHOLD)
