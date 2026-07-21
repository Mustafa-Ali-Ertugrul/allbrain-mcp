from __future__ import annotations

from datetime import datetime

from allbrain.domains.learning.learning import (
    CapabilityLearningReducer,
    make_decayed_payload,
    make_learned_payload,
    make_observed_payload,
)
from allbrain.events.schemas import EventType


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestCapabilityLearningReducer:
    def test_idempotent_same_id(self):
        r = CapabilityLearningReducer()
        ev = E(
            EventType.AGENT_CAPABILITY_LEARNED.value,
            "e1",
            make_learned_payload(agent_id="a", task_type="t", old_score=0.3, new_score=0.8, delta=0.5),
        )
        r.apply(ev)
        r.apply(ev)  # same id again
        snap = r.snapshot(agent_id="a", task_type="t")
        assert snap.capability_score == 0.8

    def test_no_events(self):
        r = CapabilityLearningReducer()
        snap = r.snapshot(agent_id="a", task_type="t")
        assert snap.capability_score == 0.0
        assert snap.observation_count == 0

    def test_observed_records_count(self):
        r = CapabilityLearningReducer()
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_OBSERVED.value,
                "e1",
                make_observed_payload(
                    agent_id="a", task_type="t", success=True, runtime_score=0.5, selection_score=0.5
                ),
            )
        )
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_OBSERVED.value,
                "e2",
                make_observed_payload(
                    agent_id="a", task_type="t", success=False, runtime_score=0.3, selection_score=0.2
                ),
            )
        )
        snap = r.snapshot(agent_id="a", task_type="t")
        assert snap.observation_count == 2

    def test_learned_sets_score(self):
        r = CapabilityLearningReducer()
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.4, new_score=0.75, delta=0.35),
            )
        )
        snap = r.snapshot(agent_id="a", task_type="t")
        assert snap.capability_score == 0.75
        assert snap.last_delta == 0.35

    def test_decayed_sets_score(self):
        r = CapabilityLearningReducer()
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_DECAYED.value,
                "e1",
                make_decayed_payload(agent_id="a", task_type="t", old_score=0.7, new_score=0.4),
            )
        )
        snap = r.snapshot(agent_id="a", task_type="t")
        assert snap.capability_score == 0.4
        # last_delta is clamped to [0, 1], so negative delta becomes 0.0
        assert snap.last_delta == 0.0

    def test_multiple_agents_isolation(self):
        r = CapabilityLearningReducer()
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="a1", task_type="t1", old_score=0.2, new_score=0.8, delta=0.6),
            )
        )
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_DECAYED.value,
                "e2",
                make_decayed_payload(agent_id="a2", task_type="t2", old_score=0.9, new_score=0.3),
            )
        )
        snap1 = r.snapshot(agent_id="a1", task_type="t1")
        snap2 = r.snapshot(agent_id="a2", task_type="t2")
        snap3 = r.snapshot(agent_id="a1", task_type="t2")
        assert snap1.capability_score == 0.8
        assert snap2.capability_score == 0.3
        assert snap3.capability_score == 0.0

    def test_learned_overrides_observed(self):
        r = CapabilityLearningReducer()
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_OBSERVED.value,
                "e1",
                make_observed_payload(
                    agent_id="a", task_type="t", success=True, runtime_score=0.8, selection_score=0.7
                ),
            )
        )
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e2",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.5, new_score=0.9, delta=0.4),
            )
        )
        snap = r.snapshot(agent_id="a", task_type="t")
        # LEARNED overwrites the pair with [(new_score, delta)]
        assert snap.capability_score == 0.9
        # observation_count after LEARNED is max(count, 1) = 1
        assert snap.observation_count == 1

    def test_all_snapshots_keys(self):
        r = CapabilityLearningReducer()
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.3, new_score=0.7, delta=0.4),
            )
        )
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e2",
                make_learned_payload(agent_id="b", task_type="u", old_score=0.5, new_score=0.6, delta=0.1),
            )
        )
        snaps = r.all_snapshots()
        assert "a::t" in snaps
        assert "b::u" in snaps
        assert len(snaps) == 2

    def test_known_keys(self):
        r = CapabilityLearningReducer()
        assert r.known_keys() == set()
        r.apply(
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="x", task_type="y", old_score=0.2, new_score=0.5, delta=0.3),
            )
        )
        assert r.known_keys() == {"x::y"}

    def test_invalid_payload_ignored(self):
        r = CapabilityLearningReducer()
        r.apply(E(EventType.AGENT_CAPABILITY_OBSERVED.value, "e1", {"agent_id": "a"}))
        snap = r.snapshot(agent_id="a", task_type="t")
        assert snap.capability_score == 0.0
        assert snap.observation_count == 0

    def test_non_learning_event_ignored(self):
        r = CapabilityLearningReducer()
        r.apply(E("some_other_event", "e1", {"agent_id": "a", "task_type": "t"}))
        snap = r.snapshot(agent_id="a", task_type="t")
        assert snap.capability_score == 0.0
