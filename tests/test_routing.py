from __future__ import annotations

import pytest

from allbrain.routing.events import (
    make_req_payload,
    make_scored_payload,
    make_selected_payload,
    validate_req,
    validate_scored,
    validate_selected,
)
from allbrain.routing.scorer import (
    best_agent,
    rank_agents,
    score_bounds,
    selection_score,
)


class TestSelectionScore:
    def test_zero(self):
        s = selection_score(reputation=0.0, runtime_score=0.0, calibrated_trust=0.0, consensus_score=0.0)
        assert s == pytest.approx(0.0)

    def test_perfect(self):
        s = selection_score(reputation=1.0, runtime_score=1.0, calibrated_trust=1.0, consensus_score=1.0)
        assert s == pytest.approx(1.0)

    def test_formula(self):
        expected = 0.5 * 0.35 + 0.6 * 0.35 + 0.7 * 0.20 + 0.8 * 0.10
        s = selection_score(reputation=0.5, runtime_score=0.6, calibrated_trust=0.7, consensus_score=0.8)
        assert s == pytest.approx(expected)

    def test_bounds(self):
        s = selection_score(reputation=2.0, runtime_score=2.0, calibrated_trust=2.0, consensus_score=2.0)
        assert s == 1.0


class TestBestAgent:
    def test_clear_winner(self):
        assert best_agent({"a": 0.9, "b": 0.5}) == "a"

    def test_empty(self):
        assert best_agent({}) is None

    def test_stable_tie_break(self):
        assert best_agent({"b": 0.9, "a": 0.9}) == "a"


class TestRankAgents:
    def test_basic(self):
        r = rank_agents({"b": 0.5, "a": 0.9, "c": 0.7})
        assert r == [("a", 0.9), ("c", 0.7), ("b", 0.5)]

    def test_tie_break(self):
        r = rank_agents({"b": 0.9, "a": 0.9})
        assert r[0][0] == "a"
        assert r[1][0] == "b"


class TestScoreBounds:
    def test_clamp(self):
        assert score_bounds(-0.5) == 0.0
        assert score_bounds(1.5) == 1.0
        assert score_bounds(0.5) == 0.5


class TestPayloads:
    def test_req(self):
        p = make_req_payload(task_id="t", task_type="x", context_key="c")
        assert p["task_id"] == "t"
        assert p["task_type"] == "x"

    def test_scored(self):
        p = make_scored_payload(agent_id="a", task_type="x", selection_score=0.8, reputation=0.7, runtime_score=0.6, calibrated_trust=0.5)
        assert p["agent_id"] == "a"
        assert p["runtime_score"] == 0.6

    def test_selected(self):
        p = make_selected_payload(task_id="t", task_type="x", agent_id="a", selection_score=0.9)
        assert p["agent_id"] == "a"
        assert p["selection_score"] == 0.9

    def test_req_validation_fails(self):
        with pytest.raises(ValueError):
            make_req_payload(task_id="", task_type="x", context_key="c")
