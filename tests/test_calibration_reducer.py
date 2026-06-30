from __future__ import annotations

from datetime import datetime

import pytest

from allbrain.calibration import (
    CALIBRATION_TEMPLATE_VERSION,
    CalibrationManager,
    CalibrationReducer,
    CalibrationState,
    calibrated_trust,
)
from allbrain.calibration import (
    make_payload as make_calibration_payload,
)
from allbrain.events.schemas import EventType
from allbrain.revision import (
    RevisionManager,
    RevisionReducer,
)
from allbrain.revision import (
    make_payload as make_revision_payload,
)
from allbrain.revision.policies import RevisionPolicy


class MockEvent:
    def __init__(self, event_type: str, id: str = "", payload: dict | None = None) -> None:
        self.type = event_type
        self.id = id
        self.payload = payload or {}
        self.created_at = datetime(2020, 1, 1)


def test_manager_equals_reducer_no_events():
    """No events -> empty CalibrationState, error=0, count=0."""
    manager = CalibrationManager()
    reducer = CalibrationReducer()

    m_state = manager.query([])
    r_state = reducer.snapshot()

    assert m_state.context_key == "default"
    assert r_state.context_key == "default"
    assert m_state.sample_count == r_state.sample_count == 0
    assert m_state.mean_confidence == r_state.mean_confidence == 0.0
    assert m_state.accuracy == r_state.accuracy == 0.0
    assert m_state.calibration_error == r_state.calibration_error == 0.0
    assert m_state.template_version == CALIBRATION_TEMPLATE_VERSION
    assert m_state == r_state


def test_manager_equals_reducer_with_samples():
    """3 CALIBRATION_UPDATED events -> manager and reducer agree exactly."""
    samples = [
        (0.9, True),
        (0.7, True),
        (0.2, False),
    ]
    events = []
    for idx, (conf, outcome) in enumerate(samples, start=1):
        events.append(
            MockEvent(
                EventType.CALIBRATION_UPDATED.value,
                id=str(idx),
                payload=make_calibration_payload(
                    context_key="default",
                    predicted_confidence=conf,
                    actual_outcome=outcome,
                ),
            )
        )

    manager = CalibrationManager()
    reducer = CalibrationReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.sample_count == r_state.sample_count == 3
    assert m_state.mean_confidence == r_state.mean_confidence == pytest.approx(0.6)
    assert m_state.accuracy == r_state.accuracy == pytest.approx(1.0)
    # error = ((0.9-1)^2 + (0.7-1)^2 + (0.2-0)^2) / 3 = (0.01 + 0.09 + 0.04) / 3 = 0.14/3
    assert m_state.calibration_error == r_state.calibration_error == pytest.approx(0.04666666666666667)
    assert m_state == r_state


def test_manager_equals_reducer_other_context_ignored():
    """Cross-context CALIBRATION_UPDATED is filtered by both views."""
    events = [
        MockEvent(
            EventType.CALIBRATION_UPDATED.value,
            id="1",
            payload=make_calibration_payload(context_key="ctx_a", predicted_confidence=0.5, actual_outcome=True),
        ),
        MockEvent(
            EventType.CALIBRATION_UPDATED.value,
            id="2",
            payload=make_calibration_payload(context_key="default", predicted_confidence=0.8, actual_outcome=True),
        ),
    ]
    manager = CalibrationManager()
    reducer = CalibrationReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events, context_key="default")
    r_state = reducer.snapshot(context_key="default")

    assert m_state.sample_count == r_state.sample_count == 1
    assert m_state.mean_confidence == r_state.mean_confidence == pytest.approx(0.8)
    assert m_state.calibration_error == r_state.calibration_error == pytest.approx(0.04)
    assert m_state == r_state


def test_calibration_applied_after_trust_in_revision():
    """Trust + calibration composition: trust=0.8, error=0.25 -> calibrated_trust=0.6."""
    # Build a log that triggers a BELIEF_REVISED + a TRUST_UPDATED + 4 CALIBRATION_UPDATED
    # such that the resulting mean squared error is exactly 0.25.
    # (0.5, True) -> 0.25 ; (0.5, True) -> 0.25 ; (1.0, True) -> 0.0 ; (1.0, True) -> 0.0
    # mean = 0.125 (not 0.25). Use (0.5, True) x 4 -> mean = 0.25.
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
    ]
    for idx in range(4):
        events.append(
            MockEvent(
                EventType.CALIBRATION_UPDATED.value,
                id=str(100 + idx),
                payload=make_calibration_payload(
                    context_key="default",
                    predicted_confidence=0.5,
                    actual_outcome=True,
                ),
            )
        )

    manager = RevisionManager()
    state = manager.query(events)

    # Sprint 46: confidence = revise(0.60, 0, 0.0) * 0.8 = 0.48
    assert state.confidence == pytest.approx(0.48)
    # Sprint 47: calibration_error = 0.25 -> calibrated_trust = 0.8 * 0.75 = 0.6
    assert state.calibration_error == pytest.approx(0.25)
    assert state.calibrated_trust == pytest.approx(0.6)
    # calibrated_trust formula = trust * (1 - error)
    assert state.calibrated_trust == pytest.approx(calibrated_trust(0.8, 0.25))
    # drift_count defaults to 0 (no BELIEF_DRIFT_DETECTED events)
    assert state.drift_count == 0
    # policy and trust_score preserved
    assert state.trust_score == pytest.approx(0.8)
    assert isinstance(state.policy, RevisionPolicy)
