from __future__ import annotations

from datetime import datetime

import pytest

from allbrain.domains.analysis.evidence import EvidenceManager, EvidenceReducer
from allbrain.events.schemas import EventType
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


def test_last_trust_updated_wins_in_reducer():
    """Two TRUST_UPDATED events for the same context: last one wins."""
    payload_a = {"context_key": "default", "weight": 0.5, "source": "task_completed"}
    trust_a = {"context_key": "default", "trust_score": 0.3}
    trust_b = {"context_key": "default", "trust_score": 0.85}

    events = [
        MockEvent(EventType.EVIDENCE_RECORDED.value, id="1", payload=payload_a),
        MockEvent(EventType.TRUST_UPDATED.value, id="2", payload=trust_a),
        MockEvent(EventType.TRUST_UPDATED.value, id="3", payload=trust_b),
    ]
    reducer = EvidenceReducer()
    for e in events:
        reducer.apply(e)
    state = reducer.snapshot()

    assert state.trust_score == pytest.approx(0.85)


def test_trust_default_when_no_trust_event():
    """Yol B: no TRUST_UPDATED in log -> trust_score = 1.0 (not 0.0)."""
    events = [
        MockEvent(
            EventType.EVIDENCE_RECORDED.value,
            id="1",
            payload={
                "context_key": "default",
                "weight": 0.8,
                "source": "task_completed",
            },
        ),
    ]
    reducer = EvidenceReducer()
    for e in events:
        reducer.apply(e)
    state = reducer.snapshot()

    assert state.trust_score == 1.0


def test_revision_confidence_multiplied_by_trust_yol_b():
    """Sprint 46 Yol B: revise() unchanged, trust applied post-revise.

    Log:
      - BELIEF_REVISED (baseline 0.80)
      - TRUST_UPDATED (0.60)
    Expected: 0.80 * 0.60 = 0.48.
    """
    revised_payload = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.80,
        reason="contradiction",
        evidence_count=0,
    )
    trust_payload = {"context_key": "default", "trust_score": 0.60}

    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised_payload),
        MockEvent(EventType.TRUST_UPDATED.value, id="2", payload=trust_payload),
    ]

    manager = RevisionManager()
    state = manager.query(events)
    assert state.confidence == pytest.approx(0.48)
    assert state.trust_score == pytest.approx(0.60)


def test_revision_no_trust_keeps_baseline():
    """No TRUST_UPDATED -> trust defaults to 1.0 -> confidence unchanged."""
    revised_payload = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.80,
        reason="contradiction",
        evidence_count=0,
    )

    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised_payload),
    ]
    manager = RevisionManager()
    state = manager.query(events)
    # No contradiction, no uncertainty, no trust -> revise(0.80, 0, 0, policy) * 1.0 = 0.80
    assert state.confidence == pytest.approx(0.80)
    assert state.trust_score == 1.0


def test_manager_and_reducer_agree_with_trust():
    """Manager.query == Reducer.snapshot even with trust multiplication.

    Log: BELIEF_REVISED (baseline 0.80) + TRUST_UPDATED (0.60).
    Expected: revise(0.80, 0, 0, policy) * 0.60 = 0.80 * 0.60 = 0.48.
    """
    revised_payload = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.80,
        reason="contradiction",
        evidence_count=0,
    )
    trust_payload = {"context_key": "default", "trust_score": 0.60}

    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised_payload),
        MockEvent(EventType.TRUST_UPDATED.value, id="2", payload=trust_payload),
    ]

    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.confidence == r_state.confidence
    assert m_state.confidence == pytest.approx(0.48)
    assert m_state.trust_score == r_state.trust_score == pytest.approx(0.60)
