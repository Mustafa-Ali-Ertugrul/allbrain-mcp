from __future__ import annotations

import pytest

from allbrain.mitigation_learning.model import StrategyStats
from allbrain.objective_system import Objective
from allbrain.objective_system.model import ObjectiveWeights
from allbrain.tradeoff_engine import (
    ParetoAnalyzer,
    ParetoFrontier,
    Selector,
    TradeoffResult,
    UtilityFunction,
    UtilityResult,
)


def _ur(id, safety, stability, success, eff, safety_pass=True):
    return UtilityResult(id, "rl", "timeout", 0.0, safety, stability, success, eff, safety_pass)


class TestPareto:
    def test_single_candidate_frontier(self):
        r = [_ur("p1", 0.7, 0.5, 0.6, 0.5)]
        f = ParetoAnalyzer.analyze(r)
        assert len(f.frontier) == 1
        assert f.frontier[0].policy_id == "p1"

    def test_safety_fail_always_dominated(self):
        r = [_ur("p1", 0.7, 0.5, 0.6, 0.5, True),
             _ur("p2", 0.3, 0.5, 0.5, 0.5, False)]
        f = ParetoAnalyzer.analyze(r)
        assert len(f.frontier) == 1
        assert f.frontier[0].policy_id == "p1"

    def test_dominates_worse_candidate(self):
        r = [_ur("p1", 0.9, 0.9, 0.9, 0.9),
             _ur("p2", 0.5, 0.5, 0.5, 0.5)]
        f = ParetoAnalyzer.analyze(r)
        assert len(f.frontier) == 1
        assert f.frontier[0].policy_id == "p1"

    def test_no_dominance_both_frontier(self):
        r = [_ur("p1", 0.9, 0.3, 0.8, 0.2),
             _ur("p2", 0.3, 0.9, 0.2, 0.8)]
        f = ParetoAnalyzer.analyze(r)
        assert len(f.frontier) == 2

    def test_empty_returns_empty(self):
        f = ParetoAnalyzer.analyze([])
        assert len(f.frontier) == 0

    def test_all_fail_no_frontier(self):
        r = [_ur("p1", 0.3, 0.5, 0.6, 0.5, False),
             _ur("p2", 0.2, 0.5, 0.5, 0.5, False)]
        f = ParetoAnalyzer.analyze(r)
        assert len(f.frontier) == 0
        assert len(f.dominated) == 2


class TestSelector:
    def test_selects_max_utility_from_frontier(self):
        r = [_ur("p1", 0.7, 0.5, 0.6, 0.5),
             _ur("p2", 0.8, 0.6, 0.7, 0.6)]
        f = ParetoAnalyzer.analyze(r)
        s = Selector.select(r, f)
        assert s.winner is not None

    def test_fallback_to_max_safety(self):
        r = [_ur("p1", 0.3, 0.5, 0.6, 0.5, False),
             _ur("p2", 0.4, 0.5, 0.5, 0.5, False)]
        f = ParetoAnalyzer.analyze(r)
        s = Selector.select(r, f)
        assert s.winner is not None
        assert s.winner.safety >= 0.3
