from __future__ import annotations

from allbrain.routing import unified_decision_score


class TestUnifiedScore:
    def test_equal_weights(self):
        s = unified_decision_score(capability=0.8, learning=0.7, dynamics=0.6, causal=0.5)
        expected = 0.8 * 0.25 + 0.7 * 0.25 + 0.6 * 0.25 + 0.5 * 0.25
        assert abs(s - expected) < 1e-9

    def test_signal_dominance(self):
        s1 = unified_decision_score(capability=0.9, learning=0.1, dynamics=0.1, causal=0.1)
        s2 = unified_decision_score(capability=0.1, learning=0.9, dynamics=0.1, causal=0.1)
        s3 = unified_decision_score(capability=0.1, learning=0.1, dynamics=0.9, causal=0.1)
        s4 = unified_decision_score(capability=0.1, learning=0.1, dynamics=0.1, causal=0.9)
        assert abs(s1 - s2) < 1e-9
        assert abs(s1 - s3) < 1e-9
        assert abs(s1 - s4) < 1e-9

    def test_bounds(self):
        s = unified_decision_score(capability=5.0, learning=-2.0, dynamics=0.5, causal=0.5)
        assert 0.0 <= s <= 1.0

    def test_missing_defaults(self):
        s = unified_decision_score()
        assert s == 0.0

    def test_custom_weights(self):
        s = unified_decision_score(
            capability=1.0,
            learning=0.0,
            dynamics=0.0,
            causal=0.0,
            capability_weight=0.5,
            learning_weight=0.2,
            dynamics_weight=0.2,
            causal_weight=0.1,
        )
        assert abs(s - 0.5) < 1e-9

    def test_all_max(self):
        s = unified_decision_score(capability=1.0, learning=1.0, dynamics=1.0, causal=1.0)
        assert abs(s - 1.0) < 1e-9

    def test_all_min(self):
        s = unified_decision_score(capability=0.0, learning=0.0, dynamics=0.0, causal=0.0)
        assert s == 0.0

    def test_weight_rebalance_fallsback(self):
        s1 = unified_decision_score(
            capability=0.8,
            learning=0.4,
            dynamics=0.4,
            causal=0.4,
            capability_weight=0.8,
            learning_weight=0.1,
            dynamics_weight=0.05,
            causal_weight=0.05,
        )
        s2 = unified_decision_score(capability=0.8, learning=0.4, dynamics=0.4, causal=0.4)
        assert s1 != s2

    def test_determinism(self):
        s1 = unified_decision_score(
            capability=0.4,
            learning=0.6,
            dynamics=0.3,
            causal=0.7,
            capability_weight=0.3,
            learning_weight=0.3,
            dynamics_weight=0.2,
            causal_weight=0.2,
        )
        s2 = unified_decision_score(
            capability=0.4,
            learning=0.6,
            dynamics=0.3,
            causal=0.7,
            capability_weight=0.3,
            learning_weight=0.3,
            dynamics_weight=0.2,
            causal_weight=0.2,
        )
        assert s1 == s2

    def test_pure_deterministic(self):
        import hashlib

        s1 = unified_decision_score(
            capability=0.42,
            learning=0.37,
            dynamics=0.91,
            causal=0.15,
            capability_weight=0.25,
            learning_weight=0.25,
            dynamics_weight=0.25,
            causal_weight=0.25,
        )
        s2 = unified_decision_score(
            capability=0.42,
            learning=0.37,
            dynamics=0.91,
            causal=0.15,
            capability_weight=0.25,
            learning_weight=0.25,
            dynamics_weight=0.25,
            causal_weight=0.25,
        )
        assert s1 == s2
