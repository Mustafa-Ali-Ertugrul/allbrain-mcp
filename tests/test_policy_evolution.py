from __future__ import annotations

import pytest

from allbrain.mitigation_learning.model import (
    POLICY_UPDATE_MIN_RECORDS,
    StrategyStats,
)
from allbrain.mitigation_learning.policy_store import PolicyStore


def _make_stats(
    ft: str, sig: str, strat: str, uses: int = 3, succ: int = 2, eff: float = 0.5, disabled: bool = False
) -> StrategyStats:
    return StrategyStats(
        fault_type=ft,
        signal_type=sig,
        strategy=strat,
        total_uses=uses,
        successes=succ,
        failures=uses - succ,
        avg_effectiveness=eff,
        success_rate=succ / max(uses, 1),
        disabled=disabled,
    )


class TestPolicyEvolution:
    def setup_method(self) -> None:
        self.store = PolicyStore()

    def test_initial_no_policy(self) -> None:
        assert self.store.get_current("timeout") is None

    def test_new_version_on_significant_change(self) -> None:
        stats = {
            ("timeout", "retry_spikes", "A"): _make_stats(
                "timeout",
                "retry_spikes",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=8,
                eff=0.8,
            ),
            ("timeout", "retry_spikes", "B"): _make_stats(
                "timeout",
                "retry_spikes",
                "B",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=2,
                eff=0.2,
            ),
        }
        p1 = self.store.update_if_needed("timeout", stats)
        assert p1 is not None
        assert p1.version == 1
        assert "A" in p1.strategy_preferences

        stats2 = {
            ("timeout", "retry_spikes", "A"): _make_stats(
                "timeout",
                "retry_spikes",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=2,
                eff=0.2,
            ),
            ("timeout", "retry_spikes", "B"): _make_stats(
                "timeout",
                "retry_spikes",
                "B",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=8,
                eff=0.8,
            ),
        }
        p2 = self.store.update_if_needed("timeout", stats2)
        assert p2 is not None
        assert p2.version == 2

    def test_no_new_version_below_min_records(self) -> None:
        stats = {
            ("timeout", "s", "A"): _make_stats(
                "timeout",
                "s",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS - 1,
                succ=5,
                eff=0.5,
            ),
        }
        p = self.store.update_if_needed("timeout", stats)
        assert p is None

    def test_policy_versions_attributes(self) -> None:
        stats = {
            ("timeout", "s", "A"): _make_stats(
                "timeout",
                "s",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=8,
                eff=0.8,
            ),
        }
        p = self.store.update_if_needed("timeout", stats)
        assert p is not None
        assert p.fault_type == "timeout"
        assert p.version == 1
        assert "A" in p.strategy_preferences
        assert "A" in p.urgency_multipliers
        assert "success_rates" in p.stats_snapshot

    def test_policy_includes_disabled_strategies(self) -> None:
        stats = {
            ("timeout", "s", "A"): _make_stats(
                "timeout",
                "s",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=1,
                eff=0.1,
                disabled=True,
            ),
            ("timeout", "s", "B"): _make_stats(
                "timeout",
                "s",
                "B",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=8,
                eff=0.8,
            ),
        }
        p = self.store.update_if_needed("timeout", stats)
        assert p is not None
        assert "A" in p.disabled_strategies

    def test_policy_includes_urgency_multipliers(self) -> None:
        stats = {
            ("timeout", "s", "A"): _make_stats(
                "timeout",
                "s",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=8,
                eff=0.5,
            ),
        }
        p = self.store.update_if_needed("timeout", stats)
        assert p is not None
        assert "A" in p.urgency_multipliers
        assert 0.5 <= p.urgency_multipliers["A"] <= 1.5

    def test_get_history(self) -> None:
        stats1 = {
            ("timeout", "s", "A"): _make_stats(
                "timeout",
                "s",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=8,
                eff=0.8,
            ),
        }
        self.store.update_if_needed("timeout", stats1)
        stats2 = {
            ("timeout", "s", "A"): _make_stats(
                "timeout",
                "s",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=2,
                eff=0.2,
            ),
        }
        self.store.update_if_needed("timeout", stats2)
        history = self.store.get_history("timeout")
        assert len(history) == 2
        assert history[0].version == 1
        assert history[1].version == 2

    def test_get_current_is_latest(self) -> None:
        stats1 = {
            ("timeout", "s", "A"): _make_stats(
                "timeout",
                "s",
                "A",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=5,
                eff=0.5,
            ),
        }
        self.store.update_if_needed("timeout", stats1)
        stats2 = {
            ("timeout", "s", "B"): _make_stats(
                "timeout",
                "s",
                "B",
                uses=POLICY_UPDATE_MIN_RECORDS,
                succ=3,
                eff=0.3,
            ),
        }
        self.store.update_if_needed("timeout", stats2)
        current = self.store.get_current("timeout")
        assert current is not None
        assert current.version == 2
        assert "B" in current.strategy_preferences
