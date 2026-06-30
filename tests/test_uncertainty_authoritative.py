from __future__ import annotations

from datetime import datetime

import pytest

from allbrain.events.schemas import EventType
from allbrain.revision import (
    RevisionManager,
    RevisionReducer,
)
from allbrain.revision import (
    make_payload as make_revision_payload,
)
from allbrain.uncertainty import (
    make_payload as make_uncertainty_payload,
)
from allbrain.uncertainty import (
    validate_payload as validate_uncertainty_payload,
)


class MockEvent:
    def __init__(self, event_type, id="", payload=None):
        self.type = event_type
        self.id = id
        self.payload = payload or {}
        self.created_at = datetime(2020, 1, 1)


def test_last_uncertainty_overrides_earlier():
    """Last UNCERTAINTY_COMPUTED in the trailing slice is authoritative (last-wins)."""
    revised = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.70,
        reason="contradiction",
        evidence_count=0,
    )
    u_first = make_uncertainty_payload(
        context_key="default",
        uncertainty=0.10,
        confidence_interval=0.05,
        evidence_count=10,
    )
    u_last = make_uncertainty_payload(
        context_key="default",
        uncertainty=0.45,
        confidence_interval=0.225,
        evidence_count=10,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=u_first),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="3", payload=u_last),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    # Last uncertainty = 0.45
    # revise(0.70, 0, 0.45, default_policy) = 0.70 - 0 - 0.45*0.15 = 0.6325
    assert m_state.confidence == pytest.approx(0.6325)
    assert r_state.confidence == pytest.approx(0.6325)


def test_uncertainty_payload_is_read_directly():
    """The UNCERTAINTY_COMPUTED payload's `uncertainty` field is read directly,
    not recomputed from belief.variance or contradiction_count.

    This is the Zorunlu: 'Manager içerisinde: if uncertainty missing: recompute() yasaktır.'
    """
    revised = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.50,
        reason="contradiction",
        evidence_count=0,
    )
    # Even though no real computation was done (the pipeline would call
    # composite_uncertainty to derive 0.30 for variance=0.20, evidence=20, contradictions=2),
    # we use a different value (0.99) to prove the manager reads the payload, not recomputes.
    uncertainty = make_uncertainty_payload(
        context_key="default",
        uncertainty=0.99,
        confidence_interval=0.495,
        evidence_count=10,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=uncertainty),
    ]
    manager = RevisionManager()
    m_state = manager.query(events)

    # The manager used 0.99, not 0.30 (which composite_uncertainty would yield).
    # revise(0.50, 0, 0.99, default_policy) = 0.50 - 0 - 0.99*0.15 = 0.3515
    assert m_state.confidence == pytest.approx(0.3515)


def test_authoritative_uncertainty_does_not_propagate_to_other_context():
    """An UNCERTAINTY_COMPUTED for context_a must not affect a query for context_b."""
    revised_a = make_revision_payload(
        context_key="ctx_a",
        old_confidence=0.90,
        new_confidence=0.50,
        reason="contradiction",
        evidence_count=0,
    )
    uncertainty_a = make_uncertainty_payload(
        context_key="ctx_a",
        uncertainty=0.99,
        confidence_interval=0.495,
        evidence_count=10,
    )
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised_a),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=uncertainty_a),
    ]
    manager = RevisionManager()

    s_a = manager.query(events, context_key="ctx_a")
    s_b = manager.query(events, context_key="ctx_b")

    # ctx_a: revise(0.50, 0, 0.99, ...) = 0.3515
    assert s_a.confidence == pytest.approx(0.3515)
    assert s_a.context_key == "ctx_a"

    # ctx_b: no checkpoint -> empty RevisionState
    assert s_b.confidence == 0.0
    assert s_b.context_key == "ctx_b"


def test_invalid_uncertainty_payload_ignored():
    """Invalid UNCERTAINTY_COMPUTED payloads are ignored (no state corruption)."""
    revised = make_revision_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.70,
        reason="contradiction",
        evidence_count=0,
    )
    invalid = {
        "context_key": "default",
        "uncertainty": 2.0,  # out of range
        "confidence_interval": 0.15,
        "evidence_count": 10,
    }
    events = [
        MockEvent(EventType.BELIEF_REVISED.value, id="1", payload=revised),
        MockEvent(EventType.UNCERTAINTY_COMPUTED.value, id="2", payload=invalid),
    ]
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    state = reducer.snapshot()
    # Invalid payload ignored -> uncertainty defaults to 0.0
    # revise(0.70, 0, 0, default_policy) = 0.70
    assert state.confidence == pytest.approx(0.70)


def test_validate_payload_uncertainty_accepts_valid():
    """Direct unit test of the validate_payload function."""
    payload = make_uncertainty_payload(
        context_key="x",
        uncertainty=0.5,
        confidence_interval=0.25,
        evidence_count=10,
    )
    validate_uncertainty_payload(payload)
