from __future__ import annotations

from datetime import datetime

import pytest

from allbrain.domains.analysis.drift import make_payload as make_drift_payload
from allbrain.domains.learning.calibration import make_payload as make_calibration_payload
from allbrain.domains.memory.replay import EventReplayEngine
from allbrain.domains.memory.revision import (
    RevisionManager,
    RevisionReducer,
)
from allbrain.domains.memory.revision import (
    make_payload as make_revision_payload,
)
from allbrain.events.schemas import EventType


class MockEvent:
    def __init__(self, event_type: str, id: str = "", payload: dict | None = None) -> None:
        self.type = event_type
        self.id = id
        self.payload = payload or {}
        self.created_at = datetime(2020, 1, 1)


def test_drift_count_from_event_log():
    """3 BELIEF_DRIFT_DETECTED events -> revision.drift_count == 3."""
    events = [
        MockEvent(
            EventType.BELIEF_REVISED.value,
            id="1",
            payload=make_revision_payload(
                context_key="default",
                old_confidence=0.90,
                new_confidence=0.50,
                reason="contradiction",
                evidence_count=0,
            ),
        ),
    ]
    for idx in range(3):
        events.append(
            MockEvent(
                EventType.BELIEF_DRIFT_DETECTED.value,
                id=str(10 + idx),
                payload=make_drift_payload(
                    context_key="default",
                    belief_before=0.5,
                    belief_after=0.7,
                    reason="trust_shift",
                ),
            )
        )

    manager = RevisionManager()
    state = manager.query(events)

    assert state.drift_count == 3


def test_drift_count_zero_default():
    """No drift events -> drift_count defaults to 0 (Yol B)."""
    events = [
        MockEvent(
            EventType.BELIEF_REVISED.value,
            id="1",
            payload=make_revision_payload(
                context_key="default",
                old_confidence=0.90,
                new_confidence=0.50,
                reason="contradiction",
                evidence_count=0,
            ),
        ),
    ]
    manager = RevisionManager()
    state = manager.query(events)

    assert state.drift_count == 0
    assert state.calibrated_trust == pytest.approx(1.0)
    assert state.calibration_error == 0.0


def test_drift_replay_round_trip():
    """Replay state['drift'] matches per-context count from event log."""
    events = [
        MockEvent(
            EventType.BELIEF_REVISED.value,
            id="1",
            payload=make_revision_payload(
                context_key="default",
                old_confidence=0.90,
                new_confidence=0.50,
                reason="contradiction",
                evidence_count=0,
            ),
        ),
        MockEvent(
            EventType.BELIEF_DRIFT_DETECTED.value,
            id="2",
            payload=make_drift_payload(
                context_key="default",
                belief_before=0.5,
                belief_after=0.8,
                reason="trust_shift",
            ),
        ),
        MockEvent(
            EventType.BELIEF_DRIFT_DETECTED.value,
            id="3",
            payload=make_drift_payload(
                context_key="default",
                belief_before=0.4,
                belief_after=0.2,
                reason="uncertainty_change",
            ),
        ),
    ]
    final_state = EventReplayEngine().replay(events)["final_state"]
    assert final_state["drift"]["default"]["count"] == 2


def test_replay_calibrated_trust_matches_revision_snapshot():
    """Netleştirme 3: final_state['revision']['calibrated_trust'] MUST equal
    RevisionReducer.snapshot() for the same event log.

    This is the strongest cross-check: the replay-engine's revision view
    (which is a snapshot of RevisionReducer) is byte-equal to a fresh
    RevisionReducer applied to the same events. Replay == live state,
    full stop.
    """
    events = [
        MockEvent(
            EventType.BELIEF_REVISED.value,
            id="1",
            payload=make_revision_payload(
                context_key="default",
                old_confidence=0.90,
                new_confidence=0.60,
                reason="contradiction",
                evidence_count=0,
            ),
        ),
        MockEvent(
            EventType.TRUST_UPDATED.value,
            id="2",
            payload={"context_key": "default", "trust_score": 0.8},
        ),
        MockEvent(
            EventType.CALIBRATION_UPDATED.value,
            id="3",
            payload=make_calibration_payload(
                context_key="default",
                predicted_confidence=0.5,
                actual_outcome=True,
            ),
        ),
        MockEvent(
            EventType.CALIBRATION_UPDATED.value,
            id="4",
            payload=make_calibration_payload(
                context_key="default",
                predicted_confidence=0.5,
                actual_outcome=True,
            ),
        ),
    ]
    final_state = EventReplayEngine().replay(events)["final_state"]
    replay_calibrated_trust = final_state["revision"]["default"]["calibrated_trust"]
    replay_calibration_error = final_state["revision"]["default"]["calibration_error"]

    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)
    r_state = reducer.snapshot()

    assert replay_calibrated_trust == pytest.approx(r_state.calibrated_trust)
    assert replay_calibration_error == pytest.approx(r_state.calibration_error)
    # Spec example: trust=0.8, error=0.25 (two (0.5,True) samples) -> calibrated_trust=0.6
    assert replay_calibrated_trust == pytest.approx(0.6)
    assert replay_calibration_error == pytest.approx(0.25)


def test_replay_calibration_round_trip():
    """final_state['calibration'] matches CalibrationReducer.all_snapshots()."""
    events = [
        MockEvent(
            EventType.CALIBRATION_UPDATED.value,
            id="1",
            payload=make_calibration_payload(
                context_key="default",
                predicted_confidence=0.8,
                actual_outcome=True,
            ),
        ),
        MockEvent(
            EventType.CALIBRATION_UPDATED.value,
            id="2",
            payload=make_calibration_payload(
                context_key="default",
                predicted_confidence=0.2,
                actual_outcome=False,
            ),
        ),
    ]
    final_state = EventReplayEngine().replay(events)["final_state"]
    from allbrain.domains.learning.calibration import CalibrationReducer

    reducer = CalibrationReducer()
    for e in events:
        reducer.apply(e)
    expected = reducer.all_snapshots()["default"]
    assert final_state["calibration"]["default"] == expected
