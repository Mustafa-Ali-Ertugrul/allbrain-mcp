from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from allbrain.value_alignment import (
    AlignmentScoreTracker,
    ConstraintEngine,
    ValueAlignmentReducer,
    make_alignment_failed_payload,
    validate_alignment_failed,
)


class TestValueAlignment:
    def test_constraint_engine_checks(self):
        ce = ConstraintEngine()
        score = ce.check("resource_exhaustion", {"safety": 0.30, "stability": 0.40}, safety_threshold=0.65)
        assert not score.passed

    def test_high_safety_passes(self):
        ce = ConstraintEngine()
        score = ce.check("policy_drift", {"safety": 0.85, "stability": 0.60}, safety_threshold=0.70)
        assert score.passed

    def test_tracker_isolation(self):
        tracker = AlignmentScoreTracker()
        from allbrain.value_alignment.model import AlignmentResult, AlignmentScore

        s1 = AlignmentScore("t1", 1.0, {}, [], [], True)
        s2 = AlignmentScore("t2", 0.1, {}, [], [], False)
        for _ in range(6):
            tracker.record(AlignmentResult(score=s1, blocked=False))
        for _ in range(6):
            tracker.record(AlignmentResult(score=s2, blocked=True))
        assert tracker.is_aligned("t1")
        assert not tracker.is_aligned("t2")

    def test_events_valid(self):
        p = make_alignment_failed_payload(
            fault_type="t", overall_score=0.3, hard_violations=["safety_min"], soft_penalties=[]
        )
        validate_alignment_failed(p)

    def test_events_invalid(self):
        with pytest.raises(ValueError, match="missing"):
            validate_alignment_failed({"fault_type": "t"})


class TestValueAlignmentReducer:
    def test_tracks_failures(self):
        r = ValueAlignmentReducer()
        ev = _make_event(
            EventType.ALIGNMENT_FAILED.value,
            {"fault_type": "t", "overall_score": 0.3, "hard_violations": ["safety_min"], "soft_penalties": []},
        )
        r.apply(ev)
        assert r.all_snapshots()["default"]["total_failures"] == 1


def _make_event(t, p):
    import types

    ev = types.SimpleNamespace()
    ev.id = f"test_{t}"
    ev.type = t
    ev.payload = p
    return ev
