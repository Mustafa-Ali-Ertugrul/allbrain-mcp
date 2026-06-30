from __future__ import annotations

import pytest

from allbrain.learning_safety.entropy import EntropyCalculator
from allbrain.learning_safety.explorer import Explorer
from allbrain.learning_safety.model import DEFAULT_BASE_EPSILON, DEFAULT_DECAY_RATE
from allbrain.mitigation_learning.model import StrategyStats


def _make_stats(ft, sig, strat, uses=5, succ=3, eff=0.5, disabled=False):
    return StrategyStats(
        fault_type=ft, signal_type=sig, strategy=strat,
        total_uses=uses, successes=succ, failures=uses - succ,
        avg_effectiveness=eff,
        success_rate=succ / max(uses, 1),
        disabled=disabled,
    )


class TestExplorer:
    def test_explorer_no_candidates_returns_recommended(self):
        calc = EntropyCalculator(base_epsilon=0.5, decay_rate=0.95)
        explorer = Explorer(calc, seed=42)
        decision = explorer.select(
            fault_type="timeout", signal_type="retry_spike",
            candidates=[], recommended="throttle_retry",
            all_stats={},
        )
        assert decision.selected_strategy == "throttle_retry"
        assert not decision.was_exploration

    def test_explorer_with_zero_epsilon_exploits(self):
        calc = EntropyCalculator(base_epsilon=0.0, decay_rate=0.95)
        explorer = Explorer(calc, seed=42)
        decision = explorer.select(
            fault_type="timeout", signal_type="retry_spike",
            candidates=["A", "B"], recommended="A",
            all_stats={},
        )
        assert not decision.was_exploration
        assert decision.selected_strategy == "A"

    def test_explorer_with_full_epsilon_explores(self):
        calc = EntropyCalculator(base_epsilon=1.0, decay_rate=0.95)
        explorer = Explorer(calc, seed=42)
        decision = explorer.select(
            fault_type="timeout", signal_type="retry_spike",
            candidates=["A", "B", "C"], recommended="A",
            all_stats={},
        )
        assert decision.was_exploration
        assert decision.selected_strategy in {"A", "B", "C"}

    def test_explorer_deterministic_with_seed(self):
        calc1 = EntropyCalculator(base_epsilon=0.5, decay_rate=0.95)
        calc2 = EntropyCalculator(base_epsilon=0.5, decay_rate=0.95)
        e1 = Explorer(calc1, seed=100)
        e2 = Explorer(calc2, seed=100)
        d1 = e1.select(
            fault_type="t", signal_type="s", candidates=["X", "Y", "Z"],
            recommended="X", all_stats={},
        )
        d2 = e2.select(
            fault_type="t", signal_type="s", candidates=["X", "Y", "Z"],
            recommended="X", all_stats={},
        )
        assert d1.selected_strategy == d2.selected_strategy
        assert d1.was_exploration == d2.was_exploration

    def test_explorer_entropy_increases_with_uniform_stats(self):
        calc = EntropyCalculator(base_epsilon=0.0)
        explorer = Explorer(calc)
        all_stats = {
            ("t", "s", "A"): _make_stats("t", "s", "A", uses=1, succ=1),
            ("t", "s", "B"): _make_stats("t", "s", "B", uses=1, succ=1),
        }
        decision = explorer.select(
            fault_type="t", signal_type="s",
            candidates=["A", "B"], recommended="A",
            all_stats=all_stats,
        )
        assert decision.entropy_at_decision > 0

    def test_explorer_advance_cycle(self):
        calc = EntropyCalculator(base_epsilon=0.20, decay_rate=0.50)
        explorer = Explorer(calc, seed=1)
        eps_before = calc.current_epsilon()
        explorer.advance_cycle()
        eps_after = calc.current_epsilon()
        assert eps_after < eps_before

    def test_explorer_decision_carries_epsilon(self):
        calc = EntropyCalculator(base_epsilon=0.30, decay_rate=0.95)
        explorer = Explorer(calc)
        decision = explorer.select(
            fault_type="t", signal_type="s", candidates=[],
            recommended="X", all_stats={},
        )
        assert decision.epsilon == pytest.approx(0.30)

    def test_explorer_with_fault_signal_match(self):
        calc = EntropyCalculator(base_epsilon=0.0)
        explorer = Explorer(calc)
        all_stats = {
            ("timeout", "retry_spike", "A"): _make_stats("timeout", "retry_spike", "A", uses=1, succ=1),
            ("timeout", "retry_spike", "B"): _make_stats("timeout", "retry_spike", "B", uses=1, succ=1),
            ("connection", "other", "C"): _make_stats("connection", "other", "C", uses=10, succ=10),
        }
        decision = explorer.select(
            fault_type="timeout", signal_type="retry_spike",
            candidates=["A", "B"], recommended="A", all_stats=all_stats,
        )
        # Two strategies matched → entropy > 0
        assert decision.entropy_at_decision > 0

    def test_explorer_default_settings(self):
        calc = EntropyCalculator()
        explorer = Explorer(calc)
        assert calc.base_epsilon == DEFAULT_BASE_EPSILON
        assert calc.decay_rate == DEFAULT_DECAY_RATE
