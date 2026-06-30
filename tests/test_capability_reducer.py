from __future__ import annotations

import pytest

from allbrain.capabilities import CapabilityManager, CapabilityReducer
from allbrain.capabilities.events import (
    make_matched_payload,
    make_registered_payload,
)
from allbrain.events.schemas import EventType


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p


class TestReducer:
    def test_empty(self):
        r = CapabilityReducer()
        s = r.snapshot(agent_id="unknown")
        assert s.capability_count == 0
        assert s.match_score == 0.0

    def test_process_events(self):
        r = CapabilityReducer()
        r.apply(E("other", "0", {"x": 1}))
        evts = [
            E(EventType.CAPABILITY_MATCHED.value, "1", make_matched_payload(agent_id="a", task_type="x", match_score=0.8, match_kind="exact")),
            E(EventType.CAPABILITY_MATCHED.value, "2", make_matched_payload(agent_id="a", task_type="x", match_score=0.3, match_kind="partial")),
        ]
        for e in evts:
            r.apply(e)
        s = r.snapshot(agent_id="a")
        assert s.capability_count == 2
        assert s.match_score == 0.8

    def test_idempotency(self):
        r = CapabilityReducer()
        e = E(EventType.CAPABILITY_MATCHED.value, "1", make_matched_payload(agent_id="a", task_type="x", match_score=0.5, match_kind="partial"))
        r.apply(e)
        r.apply(e)
        assert r.snapshot(agent_id="a").capability_count == 1

    def test_unknown_events(self):
        r = CapabilityReducer()
        r.apply(E("unknown", "99", {}))
        assert r.snapshot().capability_count == 0


class TestManagerEqualsReducer:
    def test_convergence(self):
        evts = [
            E(EventType.CAPABILITY_MATCHED.value, "1", make_matched_payload(agent_id="a", task_type="x", match_score=0.8, match_kind="exact")),
            E(EventType.CAPABILITY_MATCHED.value, "2", make_matched_payload(agent_id="a", task_type="x", match_score=0.3, match_kind="partial")),
        ]
        mgr = CapabilityManager()
        rdr = CapabilityReducer()
        for e in evts:
            rdr.apply(e)
        ms = mgr.query(evts, agent_id="a")
        rs = rdr.snapshot(agent_id="a")
        assert ms.match_score == rs.match_score
        assert ms.capability_count == rs.capability_count
