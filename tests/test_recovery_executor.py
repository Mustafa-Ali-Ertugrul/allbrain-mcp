from __future__ import annotations

import pytest

from allbrain.domains.governance.self_repair.model import (
    MIN_STABILITY_THRESHOLD,
    STABLE_BASELINE,
    RollbackPlan,
    StabilityReport,
)
from allbrain.domains.governance.self_repair.policy_health_monitor import PolicyHealthMonitor
from allbrain.domains.governance.self_repair.recovery_executor import PolicySnapshotManager, RecoveryExecutor


class TestSnapshotManager:
    def test_take_snapshot(self):
        mgr = PolicySnapshotManager()
        snap = mgr.take_snapshot(
            fault_type="timeout",
            version=1,
            stability_score=0.80,
            stats_snapshot={"rate": 0.9},
        )
        assert snap.fault_type == "timeout"
        assert snap.policy_version == 1
        assert snap.stability_score == 0.80

    def test_get_history(self):
        mgr = PolicySnapshotManager()
        mgr.take_snapshot(fault_type="timeout", version=1, stability_score=0.80, stats_snapshot={})
        mgr.take_snapshot(fault_type="timeout", version=2, stability_score=0.75, stats_snapshot={})
        history = mgr.get_history("timeout")
        assert len(history) == 2
        assert history[0].policy_version == 1

    def test_get_last_stable(self):
        mgr = PolicySnapshotManager()
        mgr.take_snapshot(fault_type="timeout", version=1, stability_score=0.85, stats_snapshot={})
        mgr.take_snapshot(fault_type="timeout", version=2, stability_score=0.65, stats_snapshot={})
        mgr.take_snapshot(fault_type="timeout", version=3, stability_score=0.72, stats_snapshot={})
        last = mgr.get_last_stable("timeout")
        assert last is not None
        assert last.policy_version == 3

    def test_get_last_stable_none_when_all_below(self):
        mgr = PolicySnapshotManager()
        mgr.take_snapshot(fault_type="timeout", version=1, stability_score=0.50, stats_snapshot={})
        assert mgr.get_last_stable("timeout") is None

    def test_snapshot_prunes_old(self):
        mgr = PolicySnapshotManager()
        for i in range(12):
            mgr.take_snapshot(fault_type="t", version=i, stability_score=0.80, stats_snapshot={})
        history = mgr.get_history("t")
        assert len(history) <= 10


class TestRecoveryExecutor:
    def test_stabilize(self):
        executor = RecoveryExecutor()
        monitor = PolicyHealthMonitor()
        monitor.check(
            "timeout",
            StabilityReport(
                fault_type="timeout",
                policy_version=2,
                stability_score=0.30,
                success_rate=0.3,
                drift_consistency=0.5,
                outcome_variance=0.2,
                safety_violations=1,
                is_stable=0.30 >= MIN_STABILITY_THRESHOLD,
            ),
        )
        plan = RollbackPlan(
            rollback_id="r1",
            fault_type="timeout",
            from_version=2,
            to_version=1,
            strategy="full",
            triggered_by="stability=0.30",
            created_at=100.0,
        )
        report = executor.stabilize(
            fault_type="timeout",
            plan=plan,
            health_monitor=monitor,
            drift_guard=None,
        )
        assert report.stabilized
        assert report.post_recovery_stability == STABLE_BASELINE
        assert monitor.get_anomaly_count("timeout") == 0
