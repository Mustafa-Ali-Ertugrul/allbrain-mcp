from __future__ import annotations

import pytest
from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.revision import (
    RevisionManager,
    RevisionReducer,
    make_payload as make_revision_payload,
)
from allbrain.uncertainty import (
    make_payload as make_uncertainty_payload,
)


class MockEvent:
    def __init__(self, event_type, id="", payload=None):
        self.type = event_type
        self.id = id
        self.payload = payload or {}
        self.created_at = datetime(2020, 1, 1)


def test_uncertainty_between_checkpoint_and_contradiction():
    """Log order: BELIEF_REVISED, UNCERTAINTY_COMPUTED(0.3), CONTRADICTION_DETECTED.
    Both views: baseline=0.60, trailing_count=1, last_uncertainty=0.3.
    """
    revised = make_revision_payload(
        context_key="default", old_confidence=0.90, new_confidence=0.60,
        reason="contradiction", evidence_count=0,
    )
    uncertainty = make_uncertainty_payload(
        context_key="default", uncertainty=0.30, confidence_interval=0.15, evidence_count=10,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=uncertainty),
        MockEvent(EventType.CONTRADICTION_DETECTED.value, id="3",
                  payload={"context_key": "default", "contradictions": []}),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.contradiction_count == r_state.contradiction_count == 1
    # revise(0.60, 1, 0.30, default_policy) = 0.60 - 0.25 - 0.30*0.15 = 0.60 - 0.25 - 0.045 = 0.305
    assert m_state.confidence == pytest.approx(0.305)
    assert r_state.confidence == pytest.approx(0.305)


def test_contradiction_between_checkpoint_and_uncertainty():
    """Log order: BELIEF_REVISED, CONTRADICTION_DETECTED, UNCERTAINTY_COMPUTED(0.4).
    Both views: baseline=0.60, trailing_count=1, last_uncertainty=0.4.
    """
    revised = make_revision_payload(
        context_key="default", old_confidence=0.90, new_confidence=0.60,
        reason="contradiction", evidence_count=0,
    )
    uncertainty = make_uncertainty_payload(
        context_key="default", uncertainty=0.40, confidence_interval=0.20, evidence_count=10,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised),
        MockEvent(EventType.CONTRADICTION_DETECTED.value, id="2",
                  payload={"context_key": "default", "contradictions": []}),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="3", payload=uncertainty),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    # revise(0.60, 1, 0.40, default_policy) = 0.60 - 0.25 - 0.40*0.15 = 0.60 - 0.25 - 0.06 = 0.29
    assert m_state.confidence == pytest.approx(0.29)
    assert r_state.confidence == pytest.approx(0.29)


def test_multiple_uncertainty_events_last_wins():
    """Multiple UNCERTAINTY_COMPUTED events in trailing slice: last one wins."""
    revised = make_revision_payload(
        context_key="default", old_confidence=0.90, new_confidence=0.60,
        reason="contradiction", evidence_count=0,
    )
    u_first = make_uncertainty_payload(
        context_key="default", uncertainty=0.10, confidence_interval=0.05, evidence_count=10,
    )
    u_second = make_uncertainty_payload(
        context_key="default", uncertainty=0.50, confidence_interval=0.25, evidence_count=10,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=u_first),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="3", payload=u_second),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    # revise(0.60, 0, 0.50, default_policy) = 0.60 - 0 - 0.50*0.15 = 0.525
    assert m_state.confidence == pytest.approx(0.525)
    assert r_state.confidence == pytest.approx(0.525)
    assert m_state.confidence == r_state.confidence


def test_uncertainty_with_mixed_trailing_events():
    """Interleaved UNCERTAINTY_COMPUTED and CONTRADICTION_DETECTED events.
    Both views converge on the same (count, last_uncertainty) pair.
    """
    revised = make_revision_payload(
        context_key="default", old_confidence=0.90, new_confidence=0.70,
        reason="contradiction", evidence_count=0,
    )
    u1 = make_uncertainty_payload(
        context_key="default", uncertainty=0.20, confidence_interval=0.10, evidence_count=10,
    )
    u2 = make_uncertainty_payload(
        context_key="default", uncertainty=0.30, confidence_interval=0.15, evidence_count=10,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised),
        MockEvent(EventType.CONTRADICTION_DETECTED.value, id="2",
                  payload={"context_key": "default", "contradictions": []}),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="3", payload=u1),
        MockEvent(EventType.CONTRADICTION_DETECTED.value, id="4",
                  payload={"context_key": "default", "contradictions": []}),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="5", payload=u2),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    # trailing: 2 contradictions, last uncertainty = 0.30
    # revise(0.70, 2, 0.30, default_policy) = 0.70 - 0.50 - 0.045 = 0.155
    assert m_state.contradiction_count == r_state.contradiction_count == 2
    assert m_state.confidence == pytest.approx(0.155)
    assert r_state.confidence == pytest.approx(0.155)