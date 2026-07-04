from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from tests.reducers.conftest import make_event


class TestCapabilityReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.capabilities.model import CapabilityState
        from allbrain.reducers.core import CapabilityReducer

        reducer = CapabilityReducer()
        snap = reducer.snapshot(agent_id="test_agent")
        assert isinstance(snap, CapabilityState)
        assert snap.capability_count == 0
        assert snap.match_score == 0.0
        assert snap.match_kind == "none"

    def test_with_capability_matched(self) -> None:
        from allbrain.reducers.core import CapabilityReducer

        reducer = CapabilityReducer()
        event = make_event(
            EventType.CAPABILITY_MATCHED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "match_score": 0.85,
                "match_kind": "exact",
                "template_version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot(agent_id="agent_a")
        assert snap.capability_count == 1
        assert snap.match_score == 0.85
        assert snap.match_kind == "exact"
        assert snap.task_type == "classification"

    def test_all_snapshots(self) -> None:
        from allbrain.reducers.core import CapabilityReducer

        reducer = CapabilityReducer()
        event = make_event(
            EventType.CAPABILITY_MATCHED.value,
            payload={
                "agent_id": "agent_a",
                "task_type": "classification",
                "match_score": 0.85,
                "match_kind": "exact",
                "template_version": 1,
            },
        )
        reducer.apply(event)
        all_snaps = reducer.all_snapshots()
        assert isinstance(all_snaps, dict)
        assert "agent_a" in all_snaps
        assert all_snaps["agent_a"]["capability_count"] == 1


class TestRevisionReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.core import RevisionReducer
        from allbrain.revision.state import RevisionState

        reducer = RevisionReducer()
        snap = reducer.snapshot(context_key="default")
        assert isinstance(snap, RevisionState)
        assert snap.confidence == 0.0
        assert snap.revision_count == 0
        assert snap.contradiction_count == 0
        assert snap.trust_score == 1.0

    def test_with_belief_revised(self) -> None:
        from allbrain.reducers.core import RevisionReducer

        reducer = RevisionReducer()
        event = make_event(
            EventType.BELIEF_REVISED.value,
            payload={
                "context_key": "default",
                "old_confidence": 0.3,
                "new_confidence": 0.7,
                "reason": "contradiction",
                "evidence_count": 5,
                "template_version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot(context_key="default")
        assert snap.revision_count == 1
        assert snap.old_confidence == 0.7  # prior confidence before update
        assert snap.confidence > 0.0

    def test_with_multiple_event_types(self) -> None:
        from allbrain.reducers.core import RevisionReducer

        reducer = RevisionReducer()

        belief_event = make_event(
            EventType.BELIEF_REVISED.value,
            payload={
                "context_key": "ctx_a",
                "old_confidence": 0.3,
                "new_confidence": 0.7,
                "reason": "contradiction",
                "evidence_count": 5,
                "template_version": 1,
            },
        )
        reducer.apply(belief_event)

        uncertainty_event = make_event(
            EventType.UNCERTAINTY_COMPUTED.value,
            payload={
                "context_key": "ctx_a",
                "uncertainty": 0.2,
                "confidence_interval": 0.1,
                "evidence_count": 3,
                "template_version": 1,
            },
        )
        reducer.apply(uncertainty_event)

        trust_event = make_event(
            EventType.TRUST_UPDATED.value,
            payload={"context_key": "ctx_a", "trust_score": 0.9},
        )
        reducer.apply(trust_event)

        snap = reducer.snapshot(context_key="ctx_a")
        assert snap.trust_score == 0.9
        assert snap.revision_count == 1

    def test_with_scalar_events(self) -> None:
        from allbrain.reducers.core import RevisionReducer

        reducer = RevisionReducer()

        reducer.apply(
            make_event(
                EventType.AGENT_REPUTATION_UPDATED.value,
                payload={"reputation_score": 0.75},
            )
        )
        reducer.apply(
            make_event(
                EventType.AGENT_SELECTED.value,
                payload={"selection_score": 0.6},
            )
        )
        snap = reducer.snapshot()
        assert snap.agent_reputation == 0.75
        assert snap.selected_agent_score == 0.6

    def test_all_snapshots(self) -> None:
        from allbrain.reducers.core import RevisionReducer

        reducer = RevisionReducer()
        reducer.apply(
            make_event(
                EventType.BELIEF_REVISED.value,
                payload={
                    "context_key": "ctx_a",
                    "old_confidence": 0.3,
                    "new_confidence": 0.7,
                    "reason": "contradiction",
                    "evidence_count": 5,
                    "template_version": 1,
                },
            )
        )
        all_snaps = reducer.all_snapshots()
        assert isinstance(all_snaps, dict)
        assert "ctx_a" in all_snaps
