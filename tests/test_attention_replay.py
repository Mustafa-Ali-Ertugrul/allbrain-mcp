from __future__ import annotations

from datetime import datetime

from allbrain.domains.analysis.attention import (
    make_attention_payload,
    make_budget_payload,
    make_reallocation_payload,
)
from allbrain.domains.memory.replay import EventReplayEngine
from allbrain.events.schemas import EventType


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestAttentionReplay:
    def test_replay_key(self):
        result = EventReplayEngine().replay([])
        assert "attention" in result["final_state"]

    def test_round_trip_attention(self):
        evts = [
            E(
                EventType.ATTENTION_ALLOCATED.value,
                "e1",
                make_attention_payload(signal="dynamics", importance=0.74, cost=0.52, allocation=0.31),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["attention"]["default"]["weights"]["dynamics"]["allocation"] == 0.31

    def test_round_trip_budget(self):
        evts = [
            E(
                EventType.RESOURCE_BUDGET_UPDATED.value,
                "e1",
                make_budget_payload(total_budget=0.8, unused_budget=0.08, allocated_total=0.72),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["attention"]["default"]["budgets"]["current"]["total_budget"] == 0.8

    def test_round_trip_reallocation(self):
        evts = [
            E(
                EventType.ATTENTION_REALLOCATED.value,
                "e1",
                make_reallocation_payload(signal="causal", delta_allocation=-0.18, new_allocation=0.22),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["attention"]["default"]["reallocations"]["causal"]["delta_allocation"] == -0.18

    def test_determinism(self):
        evts = [
            E(
                EventType.ATTENTION_ALLOCATED.value,
                "e1",
                make_attention_payload(signal="capability", importance=0.5, cost=0.2, allocation=0.25),
            ),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["attention"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["attention"]
        assert r1 == r2

    def test_mixed_with_attribution(self):
        from allbrain.domains.analysis.attribution import make_credit_payload

        evts = [
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "e1",
                make_credit_payload(decision_id="d1", signal="dynamics", contribution=0.24, confidence=0.7),
            ),
            E(
                EventType.ATTENTION_ALLOCATED.value,
                "e2",
                make_attention_payload(signal="dynamics", importance=0.74, cost=0.52, allocation=0.31),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "attribution" in f
        assert "attention" in f

    def test_empty_replay(self):
        f = EventReplayEngine().replay([])["final_state"]
        assert f["attention"] == {}

    def test_projection_only(self):
        evts = []
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["attention"] == {}
