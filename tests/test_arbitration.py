from __future__ import annotations

import pytest

from allbrain.arbitration.events import (
    make_arb_decision_payload,
    make_consensus_payload,
    make_vote_payload,
    validate_arb_decision_payload,
    validate_consensus_payload,
    validate_vote_payload,
)
from allbrain.arbitration.model import VoteRecord
from allbrain.arbitration.scorer import (
    agreement_ratio,
    candidate_scores,
    majority_resolve,
    vote_score,
    weighted_resolve,
    winner,
)


class TestVoteScore:
    def test_perfect(self):
        v = VoteRecord("a", "c", 1.0, 1.0, 1.0)
        assert vote_score(v) == pytest.approx(1.0)

    def test_zero(self):
        v = VoteRecord("a", "c", 0.0, 0.0, 0.0)
        assert vote_score(v) == pytest.approx(0.0)

    def test_mid(self):
        v = VoteRecord("a", "c", 0.5, 0.5, 0.5)
        assert vote_score(v) == pytest.approx(0.5)


class TestCandidateScores:
    def test_single_candidate(self):
        votes = [
            VoteRecord("a1", "c1", 1.0, 1.0, 1.0),
            VoteRecord("a2", "c1", 0.0, 0.0, 0.0),
        ]
        scores = candidate_scores(votes)
        assert "c1" in scores
        assert scores["c1"] == pytest.approx(0.5)

    def test_multiple_candidates(self):
        votes = [
            VoteRecord("a1", "c1", 1.0, 1.0, 1.0),
            VoteRecord("a2", "c2", 0.5, 0.5, 0.5),
        ]
        scores = candidate_scores(votes)
        assert scores["c1"] == pytest.approx(1.0)
        assert scores["c2"] == pytest.approx(0.5)


class TestWinner:
    def test_clear_winner(self):
        scores = {"c1": 1.0, "c2": 0.5}
        assert winner(scores) == "c1"

    def test_empty(self):
        assert winner({}) is None


class TestAgreementRatio:
    def test_full_agreement(self):
        votes = [VoteRecord("a1", "c1", 1.0, 1.0, 1.0)] * 3
        assert agreement_ratio(votes, "c1") == 1.0

    def test_partial(self):
        votes = [
            VoteRecord("a1", "c1", 1.0, 1.0, 1.0),
            VoteRecord("a2", "c2", 0.5, 0.5, 0.5),
        ]
        assert agreement_ratio(votes, "c1") == 0.5

    def test_empty(self):
        assert agreement_ratio([], "any") == 0.0


class TestWeightedResolve:
    def test_single_vote(self):
        votes = [VoteRecord("a1", "c1", 1.0, 1.0, 1.0)]
        w, score, ag = weighted_resolve(votes)
        assert w == "c1"
        assert score == pytest.approx(1.0)
        assert ag == 1.0

    def test_tie(self):
        votes = [
            VoteRecord("a1", "c1", 1.0, 1.0, 1.0),
            VoteRecord("a2", "c2", 1.0, 1.0, 1.0),
        ]
        w, score, ag = weighted_resolve(votes)
        assert w is not None
        assert ag == pytest.approx(0.5)


class TestMajorityResolve:
    def test_clear_winner(self):
        votes = [
            VoteRecord("a1", "c1", 1.0, 1.0, 1.0),
            VoteRecord("a2", "c1", 1.0, 1.0, 1.0),
            VoteRecord("a3", "c2", 0.0, 0.0, 0.0),
        ]
        w, score, ag = majority_resolve(votes)
        assert w == "c1"
        assert ag == pytest.approx(2 / 3)


class TestPayloads:
    def test_vote_payload_roundtrip(self):
        p = make_vote_payload(agent_id="a", candidate_id="c", context_key="ctx", confidence=0.9, reputation=0.8, calibrated_trust=0.7)
        assert p["agent_id"] == "a"
        assert p["candidate_id"] == "c"
        assert p["confidence"] == 0.9

    def test_vote_validation_fails(self):
        with pytest.raises(ValueError):
            make_vote_payload(agent_id="", candidate_id="c", context_key="ctx", confidence=0.5, reputation=0.5, calibrated_trust=0.5)

    def test_consensus_payload(self):
        p = make_consensus_payload(context_key="ctx", winner_candidate="c", score=0.9, agreement_ratio=0.75, method="weighted")
        assert p["winner_candidate"] == "c"
        assert p["score"] == 0.9

    def test_arb_decision_payload(self):
        p = make_arb_decision_payload(context_key="ctx", winner_candidate="c", method="weighted", vote_count=3, candidate_scores={"c": 0.9, "other": 0.3})
        assert p["vote_count"] == 3
