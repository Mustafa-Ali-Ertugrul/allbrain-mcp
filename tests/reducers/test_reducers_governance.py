from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from tests.reducers.conftest import make_event


class TestArbitrationReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.domains.collaboration.arbitration.model import ArbitrationState
        from allbrain.reducers.governance import ArbitrationReducer

        reducer = ArbitrationReducer()
        snap = reducer.snapshot(context_key="test_ctx")
        assert isinstance(snap, ArbitrationState)
        assert snap.vote_count == 0
        assert snap.winner_candidate is None
        assert snap.agreement_ratio == 0.0

    def test_with_vote_cast(self) -> None:
        from allbrain.reducers.governance import ArbitrationReducer

        reducer = ArbitrationReducer()
        event = make_event(
            EventType.AGENT_VOTE_CAST.value,
            payload={
                "context_key": "test_ctx",
                "agent_id": "agent_a",
                "candidate_id": "candidate_x",
                "confidence": 0.8,
                "reputation": 0.9,
                "calibrated_trust": 0.85,
                "template_version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot(context_key="test_ctx")
        assert snap.vote_count == 1
        assert snap.winner_candidate is not None

    def test_all_snapshots(self) -> None:
        from allbrain.reducers.governance import ArbitrationReducer

        reducer = ArbitrationReducer()
        reducer.apply(
            make_event(
                EventType.AGENT_VOTE_CAST.value,
                payload={
                    "context_key": "ctx_a",
                    "agent_id": "agent_a",
                    "candidate_id": "x",
                    "confidence": 0.8,
                    "reputation": 0.9,
                    "calibrated_trust": 0.85,
                    "template_version": 1,
                },
            )
        )
        all_snaps = reducer.all_snapshots()
        assert isinstance(all_snaps, dict)
        assert "ctx_a" in all_snaps


class TestBeliefReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.domains.analysis.belief.models import BeliefState
        from allbrain.reducers.governance import BeliefReducer

        reducer = BeliefReducer()
        snap = reducer.snapshot(context_key="test_ctx")
        assert isinstance(snap, BeliefState)
        assert snap.successes == 0
        assert snap.failures == 0
        assert snap.blocked == 0

    def test_with_belief_computed(self) -> None:
        from allbrain.reducers.governance import BeliefReducer

        reducer = BeliefReducer()
        event = make_event(
            EventType.BELIEF_COMPUTED.value,
            payload={
                "context_key": "test_ctx",
                "successes": 5,
                "failures": 2,
                "blocked": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot(context_key="test_ctx")
        assert snap.successes == 5
        assert snap.failures == 2
        assert snap.blocked == 1


class TestCalibrationReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.domains.learning.calibration.model import CalibrationState
        from allbrain.reducers.governance import CalibrationReducer

        reducer = CalibrationReducer()
        snap = reducer.snapshot(context_key="test_ctx")
        assert isinstance(snap, CalibrationState)
        assert snap.sample_count == 0

    def test_with_calibration_updated(self) -> None:
        from allbrain.reducers.governance import CalibrationReducer

        reducer = CalibrationReducer()
        event = make_event(
            EventType.CALIBRATION_UPDATED.value,
            payload={
                "context_key": "test_ctx",
                "predicted_confidence": 0.8,
                "actual_outcome": True,
                "template_version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot(context_key="test_ctx")
        assert snap.sample_count == 1
        assert snap.mean_confidence == 0.8


class TestContradictionReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.domains.analysis.contradiction.models import ContradictionState
        from allbrain.reducers.governance import ContradictionReducer

        reducer = ContradictionReducer()
        snap = reducer.snapshot(context_key="test_ctx")
        assert isinstance(snap, ContradictionState)
        assert snap.contradictions == []
        assert snap.severity_summary == {}

    def test_with_contradiction_detected(self) -> None:
        from allbrain.reducers.governance import ContradictionReducer

        reducer = ContradictionReducer()
        event = make_event(
            EventType.CONTRADICTION_DETECTED.value,
            payload={
                "context_key": "test_ctx",
                "contradictions": [{"left": "a", "right": "b"}],
                "severity_summary": {"high": 1},
                "evidence_event_ids": ["evt_1"],
                "template_version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot(context_key="test_ctx")
        assert len(snap.contradictions) == 1
        assert snap.severity_summary["high"] == 1


class TestDecisionReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.governance import DecisionReducer

        reducer = DecisionReducer()
        snap = reducer.snapshot(agent_id="agent_a", task_type="classify")
        assert isinstance(snap, dict)
        assert snap["score"] == {}

    def test_with_decision_computed(self) -> None:
        from allbrain.reducers.governance import DecisionReducer

        reducer = DecisionReducer()
        event = make_event(
            EventType.DECISION_COMPUTED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classify",
                "score": 0.92,
                "mode": "weighted",
                "contributors": {"reasoning": 0.5, "intuition": 0.5},
                "backend_trace": ["step_1", "step_2"],
                "template_version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot(agent_id="agent_a", task_type="classify")
        assert snap["score"]["score"] == 0.92
        assert snap["score"]["mode"] == "weighted"


class TestObjectiveSystemReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.governance import ObjectiveSystemReducer

        reducer = ObjectiveSystemReducer()
        snap = reducer.snapshot()
        assert isinstance(snap, dict)
        assert snap["total_objectives"] == 0
        assert snap["total_rebalances"] == 0
        assert snap["objectives"] == []
        assert snap["rebalances"] == []

    def test_with_objective_updated(self) -> None:
        from allbrain.reducers.governance import ObjectiveSystemReducer

        reducer = ObjectiveSystemReducer()
        event = make_event(
            EventType.OBJECTIVE_UPDATED.value,
            payload={
                "fault_type": "drift",
                "safety": 0.9,
                "stability": 0.8,
                "success": 0.7,
                "efficiency": 0.6,
                "safety_pass": True,
                "template_version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_objectives"] == 1
        assert len(snap["objectives"]) == 1


class TestValueAlignmentReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.governance import ValueAlignmentReducer

        reducer = ValueAlignmentReducer()
        snap = reducer.snapshot()
        assert isinstance(snap, dict)
        assert snap["total_failures"] == 0
        assert snap["failures"] == []

    def test_with_alignment_failed(self) -> None:
        from allbrain.reducers.governance import ValueAlignmentReducer

        reducer = ValueAlignmentReducer()
        event = make_event(
            EventType.ALIGNMENT_FAILED.value,
            payload={
                "fault_type": "value_mismatch",
                "overall_score": 0.3,
                "hard_violations": ["v1"],
                "soft_penalties": ["p1"],
                "template_version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_failures"] == 1
        assert len(snap["failures"]) == 1
