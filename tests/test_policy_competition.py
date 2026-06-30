from __future__ import annotations

import pytest

from allbrain.mitigation_learning.model import StrategyStats
from allbrain.policy_competition import (
    COMPETITION_CANDIDATE_COUNT,
    CompetitionEngine,
    PolicyCandidate,
)


def _make_stats(**overrides) -> StrategyStats:
    defaults = {
        "fault_type": "timeout",
        "signal_type": "timeout",
        "strategy": "throttle_retry",
        "total_uses": 10,
        "successes": 8,
        "failures": 2,
        "avg_effectiveness": 0.7,
        "success_rate": 0.8,
        "disabled": False,
    }
    defaults.update(overrides)
    return StrategyStats(**defaults)


class TestCompetitionEngine:
    def test_empty_candidates_returns_none(self):
        engine = CompetitionEngine()
        result = engine.compete([], {})
        assert result is None

    def test_single_candidate_wins(self):
        engine = CompetitionEngine()
        c1 = PolicyCandidate("p1", "timeout", "throttle_retry", {}, 1)
        stats = {
            ("timeout", "timeout", "throttle_retry"): _make_stats(),
        }
        result = engine.compete([c1], stats)
        assert result is not None
        assert result.winner.candidate.policy_id == "p1"
        assert result.confidence >= 0.05

    def test_higher_score_wins(self):
        engine = CompetitionEngine()
        c1 = PolicyCandidate("p_high", "timeout", "rate_limit", {}, 1)
        c2 = PolicyCandidate("p_low", "timeout", "log_warning", {}, 1)
        stats = {
            ("timeout", "timeout", "rate_limit"): _make_stats(
                strategy="rate_limit",
                success_rate=0.9,
                total_uses=15,
            ),
            ("timeout", "timeout", "log_warning"): _make_stats(
                strategy="log_warning",
                success_rate=0.3,
                total_uses=5,
            ),
        }
        result = engine.compete([c1, c2], stats)
        assert result is not None
        assert result.winner.candidate.policy_id == "p_high"

    def test_confidence_gap(self):
        engine = CompetitionEngine()
        c1 = PolicyCandidate("p1", "timeout", "throttle_retry", {}, 1)
        c2 = PolicyCandidate("p2", "timeout", "log_warning", {}, 1)
        stats = {
            ("timeout", "timeout", "throttle_retry"): _make_stats(success_rate=0.95, total_uses=50),
            ("timeout", "timeout", "log_warning"): _make_stats(success_rate=0.40, total_uses=5),
        }
        result = engine.compete([c1, c2], stats)
        assert result is not None
        assert result.confidence > 0.10

    def test_unknown_candidate_uses_defaults(self):
        engine = CompetitionEngine()
        c1 = PolicyCandidate("p1", "timeout", "unknown_strat", {}, 1)
        result = engine.compete([c1], {})
        assert result is not None
        # Unknown candidates get default 0.5 which is within [-2,2]
        assert -2.0 <= result.winner.score <= 2.0

    def test_multiple_candidates_ranked(self):
        engine = CompetitionEngine()
        candidates = [
            PolicyCandidate(f"p{i}", "timeout", f"strategy_{i}", {}, 1) for i in range(COMPETITION_CANDIDATE_COUNT)
        ]
        stats = {
            ("timeout", "timeout", f"strategy_{i}"): _make_stats(
                strategy=f"strategy_{i}",
                success_rate=0.5 + i * 0.1,
                total_uses=10 + i,
            )
            for i in range(COMPETITION_CANDIDATE_COUNT)
        }
        result = engine.compete(candidates, stats)
        assert result is not None
        scores = list(result.score_map.values())
        assert len(scores) == COMPETITION_CANDIDATE_COUNT

    def test_score_map_includes_all_candidates(self):
        engine = CompetitionEngine()
        candidates = [
            PolicyCandidate("a", "timeout", "retry", {}, 1),
            PolicyCandidate("b", "timeout", "warmup", {}, 1),
        ]
        stats = {
            ("timeout", "timeout", "retry"): _make_stats(strategy="retry"),
            ("timeout", "timeout", "warmup"): _make_stats(strategy="warmup", success_rate=0.5, total_uses=5),
        }
        result = engine.compete(candidates, stats)
        assert result is not None
        assert "a" in result.score_map
        assert "b" in result.score_map

    def test_policy_id_in_winner(self):
        engine = CompetitionEngine()
        c = PolicyCandidate("my_id", "latency", "circuit_warmup", {"key": "val"}, 2)
        stats = {
            ("latency", "latency", "circuit_warmup"): _make_stats(
                fault_type="latency",
                signal_type="latency",
                strategy="circuit_warmup",
                success_rate=0.8,
                total_uses=20,
            ),
        }
        result = engine.compete([c], stats)
        assert result is not None
        assert result.winner.candidate.policy_id == "my_id"
        assert result.winner.candidate.version == 2
