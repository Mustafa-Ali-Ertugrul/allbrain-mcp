from __future__ import annotations

import pytest

from allbrain.arbitration import ArbitrationManager, ArbitrationReducer
from allbrain.arbitration.events import (
    make_arb_decision_payload,
    make_consensus_payload,
    make_vote_payload,
)
from allbrain.events.schemas import EventType


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p


class TestReducer:
    def test_empty_snapshot(self):
        reducer = ArbitrationReducer()
        state = reducer.snapshot(context_key="unknown")
        assert state.winner_candidate is None
        assert state.vote_count == 0
        assert state.arbitration_score == 0.0

    def test_process_events(self):
        reducer = ArbitrationReducer()
        reducer.apply(E("other_event", "0", {"x": 1}))
        events = [
            E(EventType.AGENT_VOTE_CAST.value, "1", make_vote_payload(agent_id="a1", candidate_id="c1", context_key="ctx", confidence=1.0, reputation=1.0, calibrated_trust=1.0)),
            E(EventType.AGENT_VOTE_CAST.value, "2", make_vote_payload(agent_id="a2", candidate_id="c2", context_key="ctx", confidence=0.5, reputation=0.5, calibrated_trust=0.5)),
        ]
        for e in events:
            reducer.apply(e)
        state = reducer.snapshot(context_key="ctx")
        assert state.vote_count == 2
        assert state.winner_candidate is not None
        assert state.arbitration_score >= 0.0

    def test_consensus_reached(self):
        reducer = ArbitrationReducer()
        reducer.apply(E(EventType.AGENT_CONSENSUS_REACHED.value, "1", make_consensus_payload(context_key="ctx", winner_candidate="c1", score=0.9, agreement_ratio=1.0, method="weighted")))
        state = reducer.snapshot(context_key="ctx")
        assert state.winner_candidate == "c1"
        assert state.arbitration_score == 0.9
        assert state.agreement_ratio == 1.0

    def test_idempotency(self):
        reducer = ArbitrationReducer()
        event = E(EventType.AGENT_VOTE_CAST.value, "1", make_vote_payload(agent_id="a", candidate_id="c", context_key="ctx", confidence=1.0, reputation=1.0, calibrated_trust=1.0))
        reducer.apply(event)
        reducer.apply(event)
        state = reducer.snapshot(context_key="ctx")
        assert state.vote_count == 1

    def test_unknown_event_tolerance(self):
        reducer = ArbitrationReducer()
        reducer.apply(E("totally_unknown", "99", {}))
        state = reducer.snapshot()
        assert state.vote_count == 0


class TestManagerEqualsReducer:
    def test_convergence(self):
        events = [
            E(EventType.AGENT_VOTE_CAST.value, "1", make_vote_payload(agent_id="a1", candidate_id="c1", context_key="ctx", confidence=1.0, reputation=1.0, calibrated_trust=1.0)),
            E(EventType.AGENT_VOTE_CAST.value, "2", make_vote_payload(agent_id="a2", candidate_id="c2", context_key="ctx", confidence=0.5, reputation=0.5, calibrated_trust=0.5)),
        ]
        manager = ArbitrationManager()
        reducer = ArbitrationReducer()
        for e in events:
            reducer.apply(e)
        ms = manager.query(events, context_key="ctx")
        rs = reducer.snapshot(context_key="ctx")
        assert ms.winner_candidate == rs.winner_candidate
        assert ms.arbitration_score == rs.arbitration_score
        assert ms.vote_count == rs.vote_count


class TestVoteOrderIndependence:
    def test_order_independence(self):
        v1 = E(EventType.AGENT_VOTE_CAST.value, "a", make_vote_payload(agent_id="a1", candidate_id="c1", context_key="ctx", confidence=1.0, reputation=1.0, calibrated_trust=1.0))
        v2 = E(EventType.AGENT_VOTE_CAST.value, "b", make_vote_payload(agent_id="a2", candidate_id="c2", context_key="ctx", confidence=0.5, reputation=0.5, calibrated_trust=0.5))
        v3 = E(EventType.AGENT_VOTE_CAST.value, "c", make_vote_payload(agent_id="a3", candidate_id="c1", context_key="ctx", confidence=1.0, reputation=1.0, calibrated_trust=1.0))

        r1 = ArbitrationReducer()
        for e in [v1, v2, v3]:
            r1.apply(e)
        s1 = r1.snapshot(context_key="ctx")

        r2 = ArbitrationReducer()
        for e in [v3, v1, v2]:
            r2.apply(e)
        s2 = r2.snapshot(context_key="ctx")

        assert s1.winner_candidate == s2.winner_candidate
        assert s1.arbitration_score == pytest.approx(s2.arbitration_score)


class TestConsensusLastWins:
    def test_last_wins(self):
        from allbrain.revision import RevisionManager, make_payload as make_revision_payload

        events = [
            E(EventType.AGENT_CONSENSUS_REACHED.value, "1", make_consensus_payload(context_key="default", winner_candidate="c1", score=0.5, agreement_ratio=0.5, method="weighted")),
            E(EventType.AGENT_CONSENSUS_REACHED.value, "2", make_consensus_payload(context_key="default", winner_candidate="c2", score=0.9, agreement_ratio=1.0, method="weighted")),
        ]
        rev_events = list(events) + [
            E(EventType.BELIEF_REVISED.value, "rev1", make_revision_payload(context_key="default", old_confidence=0.9, new_confidence=0.6, reason="contradiction", evidence_count=0)),
        ]
        state = RevisionManager().query(rev_events)
        assert state.consensus_score == pytest.approx(0.9)