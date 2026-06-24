from __future__ import annotations

from allbrain.attribution import update_signal_reward, initial_signal_rewards, AttributionManager


class TestSignalRewards:
    def test_ema_update(self):
        new = update_signal_reward(0.5, 0.8)
        expected = 0.1 * 0.8 + 0.9 * 0.5
        assert abs(new - expected) < 1e-9

    def test_additive_meta_policy(self):
        mgr = AttributionManager()
        r = mgr.attribute([], decision_id="d1", mode="fusion", reward=0.8,
                          contributors={"capability": 0.4, "learning": 0.6}, agent_id="a", task_type="t")
        assert r["signal_rewards"]["capability"] != 0.0

    def test_isolation_per_decision(self):
        mgr = AttributionManager()
        r1 = mgr.attribute([], decision_id="d1", mode="fusion", reward=0.8,
                           contributors={"capability": 1.0}, agent_id="a", task_type="t")
        r2 = mgr.attribute([], decision_id="d2", mode="legacy", reward=0.3,
                           contributors={"capability": 1.0}, agent_id="a", task_type="t")
        assert r1["signal_rewards"]["capability"] != r2["signal_rewards"]["capability"]

    def test_initial_rewards_zero(self):
        ir = initial_signal_rewards()
        for v in ir.values():
            assert v == 0.0

    def test_cf_active_flag(self):
        mgr = AttributionManager()
        for i in range(11):
            mgr._counterfactual_count = i
        r = mgr.attribute([], decision_id="d99", mode="fusion", reward=0.5,
                          contributors={"capability": 1.0}, agent_id="x", task_type="y")
        assert isinstance(r.get("cf_active"), bool)

    def test_signal_counts_tracked(self):
        mgr = AttributionManager()
        r = mgr.attribute([], decision_id="d1", mode="fusion", reward=0.5,
                          contributors={"capability": 1.0}, agent_id="a", task_type="t")
        assert r["signal_counts"]["capability"] > 0

    def test_counterfactual_call_doesnt_crash(self):
        from allbrain.attribution.counterfactual import estimate_signal_impact
        impact = estimate_signal_impact(signal="capability", agent_id="x", task_type="y", actual_agent="x", events=[])
        assert impact == 0.0