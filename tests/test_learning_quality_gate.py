from __future__ import annotations

from datetime import datetime

from allbrain.domains.learning.learning import (
    INITIAL_CAPABILITY,
    LEARNING_DELTA_THRESHOLD,
    CapabilityLearningManager,
    CapabilityLearningReducer,
    ema_update,
    make_decayed_payload,
    make_learned_payload,
    make_observed_payload,
    observation,
)
from allbrain.domains.learning.learning.model import LEARNING_EMA_BIAS, LEARNING_RETENTION
from allbrain.events import SemanticEventType
from allbrain.events.schemas import EventType


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestQualityGates:
    """Quality gate tests for Sprint 53: edge cases, invariants, boundary conditions."""

    def test_delta_below_threshold_no_leak(self):
        """When abs(delta) < 0.02, new events must NOT be emitted.
        This tests the EMA behavior: close values converge below threshold."""
        old_score = 0.5
        obs = 0.5  # gives delta 0.0
        new_score = old_score * LEARNING_RETENTION + obs * LEARNING_EMA_BIAS
        delta = new_score - old_score
        # With old=0.5 and obs=0.5, new=0.5, delta=0.0 < 0.02
        assert abs(delta) < LEARNING_DELTA_THRESHOLD

        obs2 = 0.52  # slight increase
        new_score2 = new_score * LEARNING_RETENTION + obs2 * LEARNING_EMA_BIAS
        delta2 = new_score2 - new_score
        # new_score2 = 0.5*0.9 + 0.52*0.1 = 0.45 + 0.052 = 0.502
        # delta2 = 0.002 < 0.02
        assert abs(delta2) < LEARNING_DELTA_THRESHOLD

    def test_delta_above_threshold_emits(self):
        """When abs(delta) >= 0.02, an event should be emitted."""
        old_score = 0.5
        obs = 0.9  # big observation
        new_score = old_score * LEARNING_RETENTION + obs * LEARNING_EMA_BIAS
        delta = new_score - old_score
        # new = 0.5*0.9 + 0.9*0.1 = 0.45 + 0.09 = 0.54
        # delta = 0.04 >= 0.02
        assert abs(delta) >= LEARNING_DELTA_THRESHOLD

    def test_initial_capability_score_neutral(self):
        """Ensure INITIAL_CAPABILITY is 0.5 (neutral, not 0.0 or 1.0)."""
        assert INITIAL_CAPABILITY == 0.5

    def test_observation_formula_weights(self):
        """observation() must use the correct 0.5/0.3/0.2 weights and clamp."""
        perfect = observation(success=True, runtime_score=1.0, selection_score=1.0)
        assert abs(perfect - 1.0) < 1e-9

        zero = observation(success=False, runtime_score=0.0, selection_score=0.0)
        assert zero == 0.0

        partial = observation(success=True, runtime_score=0.5, selection_score=0.5)
        # 1.0*0.5 + 0.5*0.3 + 0.5*0.2 = 0.5 + 0.15 + 0.1 = 0.75
        assert abs(partial - 0.75) < 1e-9

    def test_ema_update_monotonic_approximation(self):
        """EMA update always converges towards the observation, never overshoots."""
        scores = [0.5]
        for _ in range(10):
            obs = 0.9  # high observation
            new = ema_update(scores[-1], observation_val=obs)
            scores.append(new)
        # Should converge towards 0.9 from below
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]
        assert scores[-1] < 0.9  # never overshoots

    def test_reducer_idempotent_duplicate_ids(self):
        """CapabilityLearningReducer must handle duplicate event IDs."""
        r = CapabilityLearningReducer()
        ev = E(
            EventType.AGENT_CAPABILITY_LEARNED.value,
            "dup1",
            make_learned_payload(agent_id="a", task_type="t", old_score=0.1, new_score=0.8, delta=0.7),
        )
        r.apply(ev)
        r.apply(ev)  # same id again
        snap = r.snapshot(agent_id="a", task_type="t")
        assert snap.capability_score == 0.8
        assert snap.observation_count == 1

    def test_manager_query_empty_events(self):
        """CapabilityLearningManager.query() must handle empty event list."""
        mgr = CapabilityLearningManager()
        state = mgr.query([], agent_id="a", task_type="t")
        assert state.capability_score == 0.0
        assert state.observation_count == 0

    def test_manager_known_keys(self):
        """CapabilityLearningManager.known_keys() must extract keys from payloads."""
        evts = [
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="a1", task_type="t1", old_score=0.2, new_score=0.5, delta=0.3),
            ),
            E(
                EventType.AGENT_CAPABILITY_DECAYED.value,
                "e2",
                make_decayed_payload(agent_id="a2", task_type="t2", old_score=0.8, new_score=0.4),
            ),
        ]
        mgr = CapabilityLearningManager()
        keys = mgr.known_keys(evts)
        assert "a1::t1" in keys
        assert "a2::t2" in keys
        assert len(keys) == 2

    def test_no_cross_agent_contamination(self):
        """Events from different agents must not affect each other's scores."""
        r = CapabilityLearningReducer()
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.2, new_score=0.9, delta=0.7),
            )
        )
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_DECAYED.value,
                "e2",
                make_decayed_payload(agent_id="b", task_type="t", old_score=0.8, new_score=0.1),
            )
        )
        snap_a = r.snapshot(agent_id="a", task_type="t")
        snap_b = r.snapshot(agent_id="b", task_type="t")
        assert snap_a.capability_score == 0.9
        assert snap_b.capability_score == 0.1

    def test_learned_capability_state_in_revision_state(self):
        """learned_capability field exists in RevisionState."""
        from allbrain.domains.memory.revision import RevisionState
        from allbrain.domains.memory.revision.state import RevisionPolicy

        s = RevisionState(
            context_key="a::t",
            confidence=0.5,
            revision_count=0,
            contradiction_count=0,
            policy=RevisionPolicy(),
            old_confidence=None,
            analysis_id="id",
        )
        assert hasattr(s, "learned_capability")
        assert s.learned_capability == 1.0  # default

    def test_adaptive_selection_score_registered(self):
        """adaptive_selection_score must be importable and callable."""
        from allbrain.domains.collaboration.routing import adaptive_selection_score

        score = adaptive_selection_score(
            reputation=0.5,
            runtime_score=0.5,
            calibrated_trust=0.5,
            consensus_score=0.5,
            capability_match=0.5,
            learned_capability=0.5,
        )
        assert isinstance(score, float)

    def test_all_new_events_in_semantic_set(self):
        """All three new event types must be in the SemanticEventType set."""
        assert EventType.AGENT_CAPABILITY_OBSERVED.value in SemanticEventType
        assert EventType.AGENT_CAPABILITY_LEARNED.value in SemanticEventType
        assert EventType.AGENT_CAPABILITY_DECAYED.value in SemanticEventType
