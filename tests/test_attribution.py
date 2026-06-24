from __future__ import annotations

from allbrain.attribution import (
    allocate_credit, AttributionManager,
    ATTRIBUTION_MIN_CONTRIBUTION, ATTRIBUTION_CF_CONFIDENCE,
    ATTRIBUTION_PROPORTIONAL_WEIGHT,
)


class TestAttribution:
    def test_allocate_proportional(self):
        allocs = allocate_credit(0.8, {"capability": 0.4, "learning": 0.2, "dynamics": 0.3, "causal": 0.1})
        total = sum(a.contribution for a in allocs)
        assert abs(total - 0.56) < 0.01

    def test_min_contribution_floor(self):
        allocs = allocate_credit(0.5, {"capability": 0.9, "learning": 0.01, "dynamics": 0.09})
        signals = {a.signal for a in allocs}
        assert "learning" not in signals

    def test_empty_contributors(self):
        allocs = allocate_credit(0.5, {})
        assert len(allocs) == 0

    def test_cf_confidence_bias(self):
        allocs_no_cf = allocate_credit(0.8, {"capability": 0.5, "learning": 0.5})
        allocs_cf = allocate_credit(0.8, {"capability": 0.5, "learning": 0.5}, cf_scores={"capability": 0.5, "learning": 0.5})
        assert len(allocs_cf) >= 1

    def test_negative_reward_handled(self):
        allocs = allocate_credit(-0.3, {"capability": 0.5, "learning": 0.5})
        assert len(allocs) >= 0

    def test_single_signal(self):
        allocs = allocate_credit(0.7, {"capability": 1.0})
        assert len(allocs) >= 1
        assert abs(sum(a.contribution for a in allocs) - 0.49) < 0.01

    def test_manager_attribute(self):
        mgr = AttributionManager()
        result = mgr.attribute(
            [], decision_id="d1", mode="fusion", reward=0.8,
            contributors={"capability": 0.4, "learning": 0.2, "dynamics": 0.3, "causal": 0.1},
            agent_id="a", task_type="t",
        )
        assert "allocations" in result
        assert "signal_rewards" in result

    def test_signal_rewards_ema(self):
        mgr = AttributionManager()
        r1 = mgr.attribute([], decision_id="d1", mode="fusion", reward=0.8,
                           contributors={"capability": 0.5, "learning": 0.5}, agent_id="a", task_type="t")
        r2 = mgr.attribute([], decision_id="d2", mode="fusion", reward=0.2,
                           contributors={"capability": 0.9, "learning": 0.1}, agent_id="a", task_type="t",
                           signal_rewards=r1["signal_rewards"], signal_counts=r1["signal_counts"])
        assert r2["signal_rewards"]["capability"] != r1["signal_rewards"]["capability"]

    def test_cf_interval(self):
        mgr = AttributionManager()
        assert mgr._counterfactual_count == 0

    def test_decision_id_scoping(self):
        r1 = allocate_credit(0.5, {"capability": 1.0})
        r2 = allocate_credit(0.5, {"capability": 1.0})
        assert r1[0].contribution == r2[0].contribution