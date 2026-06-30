from __future__ import annotations

from datetime import datetime

import pytest

from allbrain.events.schemas import EventType
from allbrain.evidence import EvidenceManager, EvidenceReducer


class MockEvent:
    def __init__(self, event_type, id="", payload=None):
        self.type = event_type
        self.id = id
        self.payload = payload or {}
        self.created_at = datetime(2020, 1, 1)


def test_same_events_same_trust_id():
    """Same event set -> same trust_score."""
    payload_evidence = {"context_key": "default", "weight": 0.8, "source": "task_completed"}
    payload_trust = {"context_key": "default", "trust_score": 0.76}
    events = [
        MockEvent(EventType.EVIDENCE_RECORDED.value, id="1", payload=payload_evidence),
        MockEvent(EventType.EVIDENCE_RECORDED.value, id="2", payload=payload_evidence),
        MockEvent(EventType.TRUST_UPDATED.value, id="3", payload=payload_trust),
    ]
    manager = EvidenceManager()

    s1 = manager.query(events)
    s2 = manager.query(events)
    s3 = manager.query(events)
    assert s1.trust_score == s2.trust_score == s3.trust_score


def test_reducer_deterministic_for_canonical_input():
    """Reducer is deterministic given the same canonical-ordered input."""
    payload_evidence = {"context_key": "default", "weight": 0.8, "source": "task_completed"}
    payload_trust = {"context_key": "default", "trust_score": 0.76}
    events = [
        MockEvent(EventType.EVIDENCE_RECORDED.value, id="1", payload=payload_evidence),
        MockEvent(EventType.TRUST_UPDATED.value, id="2", payload=payload_trust),
    ]
    canonical = events

    r1 = EvidenceReducer()
    for e in canonical:
        r1.apply(e)
    s1 = r1.snapshot()

    r2 = EvidenceReducer()
    for e in canonical:
        r2.apply(e)
    s2 = r2.snapshot()

    assert s1.evidence_count == s2.evidence_count
    assert s1.average_weight == s2.average_weight
    assert s1.trust_score == s2.trust_score


def test_manager_order_independent():
    """Manager.query sorts via canonical_event_sort — order-independent."""
    payload_evidence = {"context_key": "default", "weight": 0.8, "source": "task_completed"}
    payload_trust = {"context_key": "default", "trust_score": 0.76}
    e1 = MockEvent(EventType.EVIDENCE_RECORDED.value, id="1", payload=payload_evidence)
    e2 = MockEvent(EventType.TRUST_UPDATED.value, id="2", payload=payload_trust)
    e3 = MockEvent(EventType.EVIDENCE_RECORDED.value, id="3", payload=payload_evidence)

    manager = EvidenceManager()
    s_order_a = manager.query([e1, e2, e3])
    s_order_b = manager.query([e3, e2, e1])
    s_order_c = manager.query([e2, e3, e1])

    assert s_order_a.evidence_count == s_order_b.evidence_count == s_order_c.evidence_count
    assert s_order_a.average_weight == pytest.approx(s_order_b.average_weight)
    assert s_order_a.trust_score == pytest.approx(s_order_c.trust_score)


def test_reducer_idempotent_under_repeated_apply():
    """Applying the same event twice is a no-op (mirrors belief/contradiction)."""
    payload = {"context_key": "default", "weight": 0.8, "source": "task_completed"}
    event = MockEvent(EventType.EVIDENCE_RECORDED.value, id="1", payload=payload)
    reducer = EvidenceReducer()
    reducer.apply(event)
    s1 = reducer.snapshot()
    reducer.apply(event)
    s2 = reducer.snapshot()

    assert s1.evidence_count == s2.evidence_count == 1
    assert s1.average_weight == s2.average_weight == pytest.approx(0.8)
