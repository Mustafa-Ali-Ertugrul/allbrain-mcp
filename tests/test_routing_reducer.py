from __future__ import annotations

import pytest

from allbrain.domains.collaboration.routing import RoutingManager, RoutingReducer
from allbrain.domains.collaboration.routing.events import (
    make_scored_payload,
    make_selected_payload,
)
from allbrain.events.schemas import EventType


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p


class TestReducer:
    def test_empty(self):
        r = RoutingReducer()
        s = r.snapshot(task_type="unknown")
        assert s.selected_agent is None
        assert s.candidate_count == 0

    def test_process_events(self):
        r = RoutingReducer()
        r.apply(E("other", "0", {"x": 1}))
        evts = [
            E(
                EventType.AGENT_SELECTION_SCORED.value,
                "1",
                make_scored_payload(
                    agent_id="a",
                    task_type="x",
                    selection_score=0.9,
                    reputation=0.8,
                    runtime_score=0.7,
                    calibrated_trust=0.6,
                ),
            ),
            E(
                EventType.AGENT_SELECTION_SCORED.value,
                "2",
                make_scored_payload(
                    agent_id="b",
                    task_type="x",
                    selection_score=0.5,
                    reputation=0.4,
                    runtime_score=0.3,
                    calibrated_trust=0.2,
                ),
            ),
        ]
        for e in evts:
            r.apply(e)
        s = r.snapshot(task_type="x")
        assert s.candidate_count == 2

    def test_idempotency(self):
        r = RoutingReducer()
        e = E(
            EventType.AGENT_SELECTION_SCORED.value,
            "1",
            make_scored_payload(
                agent_id="a",
                task_type="x",
                selection_score=0.5,
                reputation=0.5,
                runtime_score=0.5,
                calibrated_trust=0.5,
            ),
        )
        r.apply(e)
        r.apply(e)
        assert r.snapshot(task_type="x").candidate_count == 1

    def test_unknown_events(self):
        r = RoutingReducer()
        r.apply(E("unknown", "99", {}))
        assert r.snapshot().candidate_count == 0


class TestManagerEqualsReducer:
    def test_convergence(self):
        evts = [
            E(
                EventType.AGENT_SELECTION_SCORED.value,
                "1",
                make_scored_payload(
                    agent_id="a",
                    task_type="x",
                    selection_score=0.9,
                    reputation=0.8,
                    runtime_score=0.7,
                    calibrated_trust=0.6,
                ),
            ),
            E(
                EventType.AGENT_SELECTION_SCORED.value,
                "2",
                make_scored_payload(
                    agent_id="b",
                    task_type="x",
                    selection_score=0.5,
                    reputation=0.4,
                    runtime_score=0.3,
                    calibrated_trust=0.2,
                ),
            ),
            E(
                EventType.AGENT_SELECTED.value,
                "3",
                make_selected_payload(task_id="t", task_type="x", agent_id="a", selection_score=0.9),
            ),
        ]
        mgr = RoutingManager()
        rdr = RoutingReducer()
        for e in evts:
            rdr.apply(e)
        ms = mgr.query(evts, task_type="x")
        rs = rdr.snapshot(task_type="x")
        assert ms.selected_agent == rs.selected_agent
        assert ms.selection_score == rs.selection_score


class TestSelectedLastWins:
    def test_last_wins(self):
        from allbrain.domains.memory.revision import RevisionManager
        from allbrain.domains.memory.revision import make_payload as make_rev

        evts = [
            E(
                EventType.AGENT_SELECTED.value,
                "1",
                make_selected_payload(task_id="t", task_type="x", agent_id="a", selection_score=0.5),
            ),
            E(
                EventType.AGENT_SELECTED.value,
                "2",
                make_selected_payload(task_id="t", task_type="x", agent_id="b", selection_score=0.9),
            ),
        ]
        rev_evts = list(evts) + [
            E(
                EventType.BELIEF_REVISED.value,
                "r1",
                make_rev(
                    context_key="default",
                    old_confidence=0.9,
                    new_confidence=0.6,
                    reason="contradiction",
                    evidence_count=0,
                ),
            ),
        ]
        st = RevisionManager().query(rev_evts)
        assert st.selected_agent_score == pytest.approx(0.9)
