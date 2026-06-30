from __future__ import annotations

import pytest

from allbrain.mitigation_learning.model import StrategyStats
from allbrain.self_play import WinMatrix
from allbrain.self_play.match_engine import MatchEngine


class TestWinMatrix:
    def test_unknown_pair_returns_0_5(self):
        wm = WinMatrix()
        assert wm.get("timeout", "a", "b") == 0.5

    def test_record_updates_win_rate(self):
        wm = WinMatrix()
        wm.record(_mr("timeout", "a", "b", "a", 0.7, 0.3))
        wr = wm.get("timeout", "a", "b")
        assert wr > 0.5

    def test_ranking_empty_returns_empty(self):
        wm = WinMatrix()
        assert wm.ranking("nonexistent") == []

    def test_ranking_orders_by_win_rate(self):
        wm = WinMatrix()
        engine = MatchEngine(wm)
        stats = {}
        for name, sr in [("alpha", 0.9), ("beta", 0.5), ("gamma", 0.1)]:
            stats[("t", "t", name)] = StrategyStats("t", "t", name, 10, int(10 * sr), 10 - int(10 * sr), sr, sr)
        candidates = ["alpha", "beta", "gamma"]
        for _ in range(5):
            engine.run_simulated_round("t", candidates, stats)
        rank = wm.ranking("t")
        assert len(rank) == 3
        assert rank[0][0] == "alpha"

    def test_symmetric_win_rate(self):
        wm = WinMatrix()
        wm.record(_mr("timeout", "a", "b", "a", 0.7, 0.3))
        wr_ab = wm.get("timeout", "a", "b")
        wr_ba = wm.get("timeout", "b", "a")
        assert abs(wr_ab + wr_ba - 1.0) < 1e-6

    def test_independent_fault_types(self):
        wm = WinMatrix()
        wm.record(_mr("timeout", "a", "b", "a", 0.7, 0.3))
        wm.record(_mr("overload", "a", "b", "b", 0.3, 0.7))
        assert wm.get("timeout", "a", "b") > 0.5
        assert wm.get("overload", "a", "b") < 0.5

    def test_edge_case_single_policy(self):
        wm = WinMatrix()
        from allbrain.self_play.model import MatchResult
        wm.record(MatchResult(
            policy_a="solo", policy_b="solo", winner="solo",
            score_a=0.5, score_b=0.5, confidence=0.0, fault_type="lonely",
        ))
        rank = wm.ranking("lonely")
        assert len(rank) <= 1

    def test_all_matrices_serializable(self):
        wm = WinMatrix()
        wm.record(_mr("timeout", "a", "b", "a", 0.7, 0.3))
        matrices = wm.all_matrices()
        assert "timeout" in matrices
        assert "a" in matrices["timeout"]


def _mr(fault_type, a, b, winner, sa, sb):
    from allbrain.self_play.model import MatchResult
    return MatchResult(
        policy_a=a, policy_b=b, winner=winner,
        score_a=sa, score_b=sb,
        confidence=abs(sa - sb), fault_type=fault_type,
    )
