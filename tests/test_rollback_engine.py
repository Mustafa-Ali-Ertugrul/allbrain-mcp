from __future__ import annotations

import pytest

from allbrain.mitigation_learning.policy_store import PolicyStore
from allbrain.self_repair.rollback_engine import RollbackEngine
from allbrain.self_repair.model import (
    StabilityReport,
    PolicySnapshot,
    MIN_STABILITY_THRESHOLD,
    STABLE_BASELINE,
)


def _report(stability):
    return StabilityReport(
        fault_type="timeout", policy_version=5,
        stability_score=stability, success_rate=0.8,
        drift_consistency=1.0, outcome_variance=0.0,
        safety_violations=0, is_stable=stability >= MIN_STABILITY_THRESHOLD,
    )


def _snap(ft, version, stability):
    return PolicySnapshot(
        snapshot_id=f"s{version}", policy_version=version,
        fault_type=ft, created_at=float(version),
        stats_snapshot={"ver": version},
        stability_score=stability,
    )


class TestRollbackEngine:
    def setup_method(self):
        self.engine = RollbackEngine()
        self.store = PolicyStore()

    def test_no_rollback_when_stable(self):
        history = [_snap("timeout", 1, 0.80), _snap("timeout", 2, 0.75)]
        plan = self.engine.plan_rollback(
            fault_type="timeout", current_version=3,
            history=history, stability=_report(0.80),
        )
        assert plan is None

    def test_rollback_plans_to_stable_target(self):
        history = [
            _snap("timeout", 1, 0.85),
            _snap("timeout", 2, 0.75),
            _snap("timeout", 3, 0.72),
        ]
        plan = self.engine.plan_rollback(
            fault_type="timeout", current_version=4,
            history=history, stability=_report(0.30),
        )
        assert plan is not None
        assert plan.to_version == 3
        assert plan.strategy == "partial"

    def test_oscillation_guard_blocks_repeat(self):
        engine = RollbackEngine(min_cycles_between=3)
        history = [_snap("timeout", 1, 0.85)]
        plan1 = engine.plan_rollback(
            fault_type="timeout", current_version=2,
            history=history, stability=_report(0.30),
        )
        assert plan1 is not None
        plan2 = engine.plan_rollback(
            fault_type="timeout", current_version=3,
            history=history, stability=_report(0.20),
        )
        assert plan2 is None

    def test_can_rollback_after_cooldown(self):
        engine = RollbackEngine(min_cycles_between=2)
        history = [_snap("timeout", 1, 0.85)]
        engine.plan_rollback(
            fault_type="timeout", current_version=2,
            history=history, stability=_report(0.30),
        )
        engine.advance_cycle()
        engine.advance_cycle()
        plan = engine.plan_rollback(
            fault_type="timeout", current_version=3,
            history=history, stability=_report(0.20),
        )
        assert plan is not None

    def test_falls_back_to_version_1(self):
        history = [
            _snap("timeout", 1, 0.60),
            _snap("timeout", 2, 0.55),
            _snap("timeout", 3, 0.50),
        ]
        plan = self.engine.plan_rollback(
            fault_type="timeout", current_version=4,
            history=history, stability=_report(0.20),
        )
        assert plan is not None
        assert plan.to_version == 1

    def test_full_strategy_when_critical(self):
        history = [_snap("timeout", 1, 0.85)]
        plan = self.engine.plan_rollback(
            fault_type="timeout", current_version=2,
            history=history, stability=_report(0.20),
        )
        assert plan is not None
        assert plan.strategy == "full"

    def test_partial_strategy_when_moderate(self):
        history = [_snap("timeout", 1, 0.85)]
        plan = self.engine.plan_rollback(
            fault_type="timeout", current_version=2,
            history=history, stability=_report(0.35),
        )
        assert plan is not None
        assert plan.strategy == "partial"

    def test_no_rollback_when_no_history(self):
        plan = self.engine.plan_rollback(
            fault_type="timeout", current_version=2,
            history=[], stability=_report(0.20),
        )
        assert plan is None

    def test_advance_cycle_increments(self):
        assert self.engine.total_cycle_count == 0
        self.engine.advance_cycle()
        assert self.engine.total_cycle_count == 1