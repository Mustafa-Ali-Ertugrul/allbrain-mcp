from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from allbrain.reputation import ReputationManager, ReputationReducer
from allbrain.reputation.events import make_payload


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p


def s(success, confidence, duration, retry):
    return (success, confidence, duration, retry)


class TestReducer:
    def test_empty_snapshot(self):
        reducer = ReputationReducer()
        state = reducer.snapshot(agent_id="unknown")
        assert state.agent_id == "unknown"
        assert state.task_count == 0
        assert state.success_rate == 0.0
        assert state.mean_confidence == 0.0
        assert state.reputation_score == 0.0

    def test_process_events(self):
        reducer = ReputationReducer()
        reducer.apply(E("other_event", "0", {"x": 1}))
        events = [
            E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="a1", task_id="t1", success=True, confidence=0.9, duration_ms=100, retry_count=0, reputation_score=0.0, analysis_id="x")),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "2", make_payload(agent_id="a1", task_id="t2", success=False, confidence=0.5, duration_ms=200, retry_count=1, reputation_score=0.0, analysis_id="y")),
        ]
        for e in events:
            reducer.apply(e)
        state = reducer.snapshot(agent_id="a1")
        assert state.task_count == 2
        assert state.success_rate == 0.5
        assert state.mean_confidence == pytest.approx(0.7)
        assert state.mean_duration_ms == pytest.approx(150.0)
        assert state.mean_retry_count == pytest.approx(0.5)

    def test_cross_agent_isolation(self):
        reducer = ReputationReducer()
        reducer.apply(E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="a1", task_id="t1", success=True, confidence=1.0, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="x")))
        reducer.apply(E(EventType.AGENT_REPUTATION_UPDATED.value, "2", make_payload(agent_id="a2", task_id="t2", success=False, confidence=0.0, duration_ms=0, retry_count=5, reputation_score=0.0, analysis_id="y")))
        assert reducer.snapshot(agent_id="a1").reputation_score == pytest.approx(1.0)
        assert reducer.snapshot(agent_id="a2").reputation_score == pytest.approx(0.0)

    def test_idempotency(self):
        reducer = ReputationReducer()
        event = E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="a1", task_id="t1", success=True, confidence=1.0, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="x"))
        reducer.apply(event)
        reducer.apply(event)
        state = reducer.snapshot(agent_id="a1")
        assert state.task_count == 1

    def test_unknown_event_tolerance(self):
        reducer = ReputationReducer()
        reducer.apply(E("totally_unknown_event", "99", {"some": "data"}))
        state = reducer.snapshot(agent_id="any")
        assert state.task_count == 0
        assert state.reputation_score == 0.0

    def test_all_snapshots(self):
        reducer = ReputationReducer()
        reducer.apply(E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="a", task_id="t", success=True, confidence=1.0, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="x")))
        reducer.apply(E(EventType.AGENT_REPUTATION_UPDATED.value, "2", make_payload(agent_id="b", task_id="t", success=False, confidence=0.0, duration_ms=0, retry_count=5, reputation_score=0.0, analysis_id="y")))
        snaps = reducer.all_snapshots()
        assert set(snaps.keys()) == {"a", "b"}
        assert snaps["a"]["reputation_score"] == pytest.approx(1.0)
        assert snaps["b"]["reputation_score"] == pytest.approx(0.0)


class TestManagerEqualsReducer:
    def test_convergence(self):
        events = [
            E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="a1", task_id="t1", success=True, confidence=1.0, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="x")),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "2", make_payload(agent_id="a1", task_id="t2", success=False, confidence=0.5, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="y")),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "3", make_payload(agent_id="a1", task_id="t3", success=True, confidence=0.7, duration_ms=0, retry_count=1, reputation_score=0.0, analysis_id="z")),
        ]
        manager = ReputationManager()
        reducer = ReputationReducer()
        for e in events:
            reducer.apply(e)
        ms = manager.query(events, agent_id="a1")
        rs = reducer.snapshot(agent_id="a1")
        assert ms.success_rate == rs.success_rate
        assert ms.mean_confidence == rs.mean_confidence
        assert ms.mean_retry_count == rs.mean_retry_count
        assert ms.reputation_score == rs.reputation_score

    def test_convergence_with_unknown_events(self):
        events = [
            E("random_event", "0", {}),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="a1", task_id="t", success=True, confidence=1.0, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="x")),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "2", make_payload(agent_id="a2", task_id="t", success=False, confidence=0.0, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="y")),
            E("another_random", "3", {}),
        ]
        manager = ReputationManager()
        reducer = ReputationReducer()
        for e in events:
            reducer.apply(e)
        for agent_id in ("a1", "a2"):
            assert manager.query(events, agent_id=agent_id).reputation_score == reducer.snapshot(agent_id=agent_id).reputation_score


class TestLastWins:
    """Sprint 48: reputation_score last-wins across events."""

    def test_last_wins(self):
        from allbrain.reputation.estimator import reputation_score as compute_score
        from allbrain.reputation.events import make_payload as make_reputation_payload

        s1 = (True, 0.5, 0.0, 0.0)
        score1 = compute_score([s1])
        s2 = (True, 0.75, 0.0, 0.0)
        score2 = compute_score([s1, s2])
        s3 = (True, 0.82, 0.0, 0.0)
        score3 = compute_score([s1, s2, s3])

        events = [
            E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_reputation_payload(agent_id="a", task_id="t1", success=s1[0], confidence=s1[1], duration_ms=s1[2], retry_count=s1[3], reputation_score=score1, analysis_id="x")),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "2", make_reputation_payload(agent_id="a", task_id="t2", success=s2[0], confidence=s2[1], duration_ms=s2[2], retry_count=s2[3], reputation_score=score2, analysis_id="y")),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "3", make_reputation_payload(agent_id="a", task_id="t3", success=s3[0], confidence=s3[1], duration_ms=s3[2], retry_count=s3[3], reputation_score=score3, analysis_id="z")),
        ]
        from allbrain.revision import RevisionManager
        from allbrain.revision import make_payload as make_revision_payload
        rev_manager = RevisionManager()
        base_events = list(events) + [
            E(EventType.BELIEF_REVISED.value, "rev1", make_revision_payload(context_key="default", old_confidence=0.9, new_confidence=0.6, reason="contradiction", evidence_count=0)),
        ]
        state = rev_manager.query(base_events)
        assert state.agent_reputation == pytest.approx(score3)
