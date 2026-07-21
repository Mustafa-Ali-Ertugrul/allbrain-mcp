from __future__ import annotations

import pytest

from allbrain.domains.governance.self_repair.model import MIN_STABILITY_THRESHOLD, StabilityReport
from allbrain.domains.governance.self_repair.policy_health_monitor import PolicyHealthMonitor


def _report(stability):
    return StabilityReport(
        fault_type="timeout",
        policy_version=1,
        stability_score=stability,
        success_rate=0.8,
        drift_consistency=1.0,
        outcome_variance=0.0,
        safety_violations=0,
        is_stable=stability >= MIN_STABILITY_THRESHOLD,
    )


class TestPolicyHealthMonitor:
    def setup_method(self):
        self.monitor = PolicyHealthMonitor()

    def test_no_anomaly_above_threshold(self):
        assert not self.monitor.check("timeout", _report(0.80))

    def test_anomaly_below_threshold(self):
        assert self.monitor.check("timeout", _report(0.30))

    def test_anomaly_count_increments(self):
        self.monitor.check("timeout", _report(0.30))
        assert self.monitor.get_anomaly_count("timeout") == 1
        self.monitor.check("timeout", _report(0.20))
        assert self.monitor.get_anomaly_count("timeout") == 2

    def test_stable_clears_count(self):
        self.monitor.check("timeout", _report(0.30))
        self.monitor.check("timeout", _report(0.80))
        assert self.monitor.get_anomaly_count("timeout") == 0

    def test_reset_fault(self):
        self.monitor.check("timeout", _report(0.30))
        self.monitor.check("timeout", _report(0.30))
        self.monitor.reset_fault("timeout")
        assert self.monitor.get_anomaly_count("timeout") == 0

    def test_record_safety_violation(self):
        self.monitor.record_safety_violation("timeout")
        self.monitor.record_safety_violation("timeout")
        assert self.monitor.get_safety_violations("timeout") == 2

    def test_is_stable(self):
        self.monitor.check("timeout", _report(0.80))
        assert self.monitor.is_stable("timeout")

    def test_get_anomaly_count_default_zero(self):
        assert self.monitor.get_anomaly_count("unknown") == 0
