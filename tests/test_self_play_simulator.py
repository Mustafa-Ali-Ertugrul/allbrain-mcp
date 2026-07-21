from __future__ import annotations

import pytest

from allbrain.domains.governance.mitigation_learning.model import StrategyStats
from allbrain.domains.learning.self_play import (
    SELF_PLAY_MIN_CANDIDATES,
    MatchEngine,
    MatchResult,
    SelfPlayReducer,
    Simulator,
    WinMatrix,
    make_match_played_payload,
    validate_match_played,
)
from allbrain.events.schemas import EventType


class TestSimulator:
    def test_deterministic_same_input_same_output(self):
        sim = Simulator()
        stats = {
            ("timeout", "timeout", "a"): StrategyStats("timeout", "timeout", "a", 10, 8, 2, 0.7, 0.8),
            ("timeout", "timeout", "b"): StrategyStats("timeout", "timeout", "b", 5, 2, 3, 0.3, 0.4),
        }
        r1 = sim.simulate("timeout", "a", "b", stats)
        r2 = sim.simulate("timeout", "a", "b", stats)
        assert r1.winner == r2.winner
        assert r1.score_a == r2.score_a

    def test_higher_success_rate_wins(self):
        sim = Simulator()
        stats = {
            ("timeout", "timeout", "high"): StrategyStats("timeout", "timeout", "high", 100, 90, 10, 0.8, 0.9),
            ("timeout", "timeout", "low"): StrategyStats("timeout", "timeout", "low", 5, 1, 4, 0.2, 0.2),
        }
        r = sim.simulate("timeout", "high", "low", stats)
        assert r.winner == "high"

    def test_disabled_penalty(self):
        sim = Simulator()
        stats = {
            ("timeout", "timeout", "enabled"): StrategyStats("timeout", "timeout", "enabled", 10, 8, 2, 0.7, 0.8),
            ("timeout", "timeout", "disabled"): StrategyStats(
                "timeout", "timeout", "disabled", 10, 8, 2, 0.7, 0.8, disabled=True
            ),
        }
        r = sim.simulate("timeout", "enabled", "disabled", stats)
        assert r.winner == "enabled"

    def test_confidence_scales_with_gap(self):
        sim = Simulator()
        stats_close = {
            ("x", "x", "a"): StrategyStats("x", "x", "a", 10, 6, 4, 0.6, 0.6),
            ("x", "x", "b"): StrategyStats("x", "x", "b", 10, 6, 4, 0.55, 0.55),
        }
        stats_far = {
            ("y", "y", "a"): StrategyStats("y", "y", "a", 10, 9, 1, 0.8, 0.9),
            ("y", "y", "b"): StrategyStats("y", "y", "b", 1, 0, 1, 0.0, 0.0),
        }
        r_close = sim.simulate("x", "a", "b", stats_close)
        r_far = sim.simulate("y", "a", "b", stats_far)
        assert r_far.confidence > r_close.confidence


class TestMatchEngine:
    def test_too_few_candidates_returns_empty(self):
        engine = MatchEngine()
        stats = {("t", "t", "a"): StrategyStats("t", "t", "a", 1, 1, 0, 0.5, 1.0)}
        results = engine.run_simulated_round("t", ["a"], stats)
        assert results == []

    def test_two_candidates_produces_match(self):
        engine = MatchEngine()
        stats = {
            ("t", "t", "a"): StrategyStats("t", "t", "a", 10, 8, 2, 0.7, 0.8),
            ("t", "t", "b"): StrategyStats("t", "t", "b", 5, 2, 3, 0.3, 0.4),
        }
        results = engine.run_simulated_round("t", ["a", "b"], stats)
        assert len(results) == 1
        assert results[0].fault_type == "t"

    def test_win_matrix_updated_after_match(self):
        wm = WinMatrix()
        engine = MatchEngine(wm)
        stats = {
            ("t", "t", "a"): StrategyStats("t", "t", "a", 10, 8, 2, 0.7, 0.8),
            ("t", "t", "b"): StrategyStats("t", "t", "b", 5, 2, 3, 0.3, 0.4),
        }
        engine.run_simulated_round("t", ["a", "b"], stats)
        wr = wm.get("t", "a", "b")
        assert wr > 0.5


class TestMatchesEvents:
    def test_valid_payload(self):
        p = make_match_played_payload(
            policy_a="a",
            policy_b="b",
            winner="a",
            score_a=0.7,
            score_b=0.3,
            confidence=0.4,
            fault_type="timeout",
        )
        validate_match_played(p)

    def test_invalid_missing_key(self):
        with pytest.raises(ValueError, match="missing"):
            validate_match_played({"policy_a": "a"})

    def test_invalid_score_range(self):
        with pytest.raises(ValueError):
            make_match_played_payload(
                policy_a="a",
                policy_b="b",
                winner="a",
                score_a=5.0,
                score_b=0.3,
                confidence=0.4,
                fault_type="timeout",
            )


class TestSelfPlayReducer:
    def test_tracks_matches(self):
        reducer = SelfPlayReducer()
        ev = _make_event(
            EventType.MATCH_PLAYED.value,
            {
                "policy_a": "a",
                "policy_b": "b",
                "winner": "a",
                "score_a": 0.7,
                "score_b": 0.3,
                "confidence": 0.4,
                "fault_type": "timeout",
            },
        )
        reducer.apply(ev)
        snap = reducer.all_snapshots()
        assert snap["default"]["total_matches"] == 1


def _make_event(type_str: str, payload: dict):
    import types

    ev = types.SimpleNamespace()
    ev.id = f"test_{type_str}_{hash(str(payload))}"
    ev.type = type_str
    ev.payload = payload
    ev.created_at = None
    ev.agent_id = None
    ev.session_id = None
    return ev
