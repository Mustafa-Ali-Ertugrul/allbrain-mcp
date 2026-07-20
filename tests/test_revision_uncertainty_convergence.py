from __future__ import annotations

from datetime import datetime

import pytest

from allbrain.domains.reasoning.uncertainty import (
    make_payload as make_uncertainty_payload,
)
from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine
from allbrain.revision import (
    RevisionManager,
    RevisionPolicy,
    RevisionReducer,
)
from allbrain.revision import (
    make_payload as make_revision_payload,
)


class MockEvent:
    def __init__(self, event_type, id="", payload=None):
        self.type = event_type
        self.id = id
        self.payload = payload or {}
        self.created_at = datetime(2020, 1, 1)


def test_manager_equals_reducer_with_uncertainty():
    """Log with UNCERTAINTY_COMPUTED between BELIEF_REVISED and CONTRADICTION_DETECTED.
    Both views agree on uncertainty and final confidence.
    """
    revised_payload = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.55,
        reason="contradiction",
        evidence_count=0,
    )
    uncertainty_payload = make_uncertainty_payload(
        context_key="default",
        uncertainty=0.30,
        confidence_interval=0.15,
        evidence_count=10,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised_payload),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=uncertainty_payload),
        MockEvent(
            EventType.CONTRADICTION_DETECTED.value, id="3", payload={"context_key": "default", "contradictions": []}
        ),
    ]

    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.confidence == pytest.approx(r_state.confidence)
    assert m_state.contradiction_count == r_state.contradiction_count == 1
    assert m_state.analysis_id == r_state.analysis_id


def test_no_uncertainty_defaults_to_zero():
    """Zorunlu: if no UNCERTAINTY_COMPUTED in the log, both views use 0.0
    (NOT a recompute from belief.variance or contradiction_count).
    """
    revised_payload = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.60,
        reason="contradiction",
        evidence_count=0,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised_payload),
        MockEvent(
            EventType.CONTRADICTION_DETECTED.value, id="2", payload={"context_key": "default", "contradictions": []}
        ),
        MockEvent(EventType.TASK_COMPLETED.value, id="3"),
    ]

    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    # Without uncertainty, revise(0.60, 1, 0, policy) = 0.60 - 0.25 = 0.35
    assert m_state.confidence == pytest.approx(0.35)
    assert r_state.confidence == pytest.approx(0.35)
    assert m_state.confidence == r_state.confidence


def test_replay_round_trip_with_uncertainty():
    """NetleÅŸtirme 2: exact dict equality through the replay engine.

    final_state["revision"]["default"] == manager.query(events, "default").state-dict
    """
    revised_payload = make_revision_payload(
        context_key="default",
        old_confidence=0.84,
        new_confidence=0.52,
        reason="contradiction",
        evidence_count=6,
    )
    uncertainty_payload = make_uncertainty_payload(
        context_key="default",
        uncertainty=0.25,
        confidence_interval=0.125,
        evidence_count=20,
    )
    events = [
        MockEvent(EventType.TASK_COMPLETED.value, id="1"),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=uncertainty_payload),
        MockEvent(EventType.BELIEF_REVISED.value, id="3", payload=revised_payload),
        MockEvent(
            EventType.CONTRADICTION_DETECTED.value, id="4", payload={"context_key": "default", "contradictions": []}
        ),
    ]

    engine = EventReplayEngine()
    final_state = engine.replay(events)["final_state"]

    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)
    expected = reducer.all_snapshots()["default"]

    assert final_state["revision"]["default"] == expected


def test_uncertainty_in_payload_changes_confidence():
    """Two logs identical except uncertainty value -> different final confidence."""
    base_revised = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.60,
        reason="contradiction",
        evidence_count=0,
    )
    u_high = make_uncertainty_payload(
        context_key="default",
        uncertainty=0.50,
        confidence_interval=0.25,
        evidence_count=10,
    )
    u_low = make_uncertainty_payload(
        context_key="default",
        uncertainty=0.10,
        confidence_interval=0.05,
        evidence_count=10,
    )

    events_high = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=base_revised),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=u_high),
    ]
    events_low = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=base_revised),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=u_low),
    ]

    manager = RevisionManager()
    s_high = manager.query(events_high)
    s_low = manager.query(events_low)

    # High uncertainty -> lower confidence (more penalty)
    assert s_high.confidence < s_low.confidence

