from __future__ import annotations

from allbrain.mitigation_learning.model import MIN_USES_FOR_OPTIMIZER, StrategyStats
from allbrain.mitigation_learning.strategy_optimizer import StrategyOptimizer


def _make_stats(
    ft: str,
    sig: str,
    strat: str,
    *,
    uses: int = 5,
    successes: int = 3,
    eff: float = 0.5,
    disabled: bool = False,
) -> tuple[tuple[str, str, str], StrategyStats]:
    stats = StrategyStats(
        fault_type=ft,
        signal_type=sig,
        strategy=strat,
        total_uses=uses,
        successes=successes,
        failures=uses - successes,
        avg_effectiveness=eff,
        success_rate=successes / max(uses, 1),
        disabled=disabled,
    )
    return ((ft, sig, strat), stats)


class TestStrategyOptimizer:
    def setup_method(self) -> None:
        self.opt = StrategyOptimizer()

    def test_recommend_default_when_no_history(self) -> None:
        result = self.opt.recommend(
            fault_type="timeout",
            signal_type="retry_spikes",
            default_strategy="throttle_retry",
            all_stats={},
        )
        assert result == "throttle_retry"

    def test_recommend_best_strategy_by_score(self) -> None:
        all_stats = dict(
            [
                _make_stats("timeout", "retry_spikes", "throttle_retry", uses=5, successes=4, eff=0.7),
                _make_stats("timeout", "retry_spikes", "circuit_warmup", uses=5, successes=2, eff=0.4),
            ]
        )
        result = self.opt.recommend(
            fault_type="timeout",
            signal_type="retry_spikes",
            default_strategy="throttle_retry",
            all_stats=all_stats,
        )
        assert result == "throttle_retry"

    def test_skip_disabled_strategy(self) -> None:
        all_stats = dict(
            [
                _make_stats("timeout", "retry_spikes", "throttle_retry", uses=5, successes=4, eff=0.7, disabled=True),
                _make_stats("timeout", "retry_spikes", "circuit_warmup", uses=5, successes=2, eff=0.4),
            ]
        )
        result = self.opt.recommend(
            fault_type="timeout",
            signal_type="retry_spikes",
            default_strategy="throttle_retry",
            all_stats=all_stats,
        )
        assert result == "circuit_warmup"

    def test_below_min_uses_not_considered(self) -> None:
        all_stats = dict(
            [
                _make_stats(
                    "timeout", "retry_spikes", "throttle_retry", uses=MIN_USES_FOR_OPTIMIZER - 1, successes=3, eff=0.9
                ),
            ]
        )
        result = self.opt.recommend(
            fault_type="timeout",
            signal_type="retry_spikes",
            default_strategy="circuit_warmup",
            all_stats=all_stats,
        )
        assert result == "circuit_warmup"

    def test_fallback_when_all_disabled(self) -> None:
        all_stats = dict(
            [
                _make_stats("timeout", "retry_spikes", "throttle_retry", uses=5, successes=1, eff=0.1, disabled=True),
                _make_stats("timeout", "retry_spikes", "circuit_warmup", uses=5, successes=0, eff=0.0, disabled=True),
            ]
        )
        result = self.opt.recommend(
            fault_type="timeout",
            signal_type="retry_spikes",
            default_strategy="log_warning",
            all_stats=all_stats,
        )
        assert result == "log_warning"

    def test_tied_scores_returns_first(self) -> None:
        k1 = _make_stats("timeout", "retry_spikes", "A", uses=5, successes=3, eff=0.5)
        k2 = _make_stats("timeout", "retry_spikes", "B", uses=5, successes=3, eff=0.5)
        all_stats = {}
        all_stats[k1[0]] = k1[1]
        all_stats[k2[0]] = k2[1]
        result = self.opt.recommend(
            fault_type="timeout",
            signal_type="retry_spikes",
            default_strategy="A",
            all_stats=all_stats,
        )
        assert result in ("A", "B")

    def test_unknown_fault_type_returns_default(self) -> None:
        all_stats = dict(
            [
                _make_stats("timeout", "retry_spikes", "throttle_retry", uses=10, successes=9, eff=0.9),
            ]
        )
        result = self.opt.recommend(
            fault_type="connection",
            signal_type="connection_drop",
            default_strategy="rate_limit",
            all_stats=all_stats,
        )
        assert result == "rate_limit"

    def test_matches_exact_fault_and_signal(self) -> None:
        all_stats = dict(
            [
                _make_stats("timeout", "retry_spikes", "throttle_retry", uses=5, successes=4, eff=0.8),
                _make_stats("timeout", "latency", "circuit_warmup", uses=5, successes=2, eff=0.3),
                _make_stats("connection", "retry_spikes", "rate_limit", uses=5, successes=3, eff=0.6),
            ]
        )
        result = self.opt.recommend(
            fault_type="timeout",
            signal_type="latency",
            default_strategy="circuit_warmup",
            all_stats=all_stats,
        )
        assert result == "circuit_warmup"

    def test_score_below_zero_falls_back(self) -> None:
        k1 = _make_stats("timeout", "retry_spikes", "throttle_retry", uses=5, successes=0, eff=-0.5)
        all_stats = {}
        all_stats[k1[0]] = k1[1]
        result = self.opt.recommend(
            fault_type="timeout",
            signal_type="retry_spikes",
            default_strategy="circuit_warmup",
            all_stats=all_stats,
        )
        assert result == "circuit_warmup"
