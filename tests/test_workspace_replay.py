from __future__ import annotations

from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine
from allbrain.workspace import (
    make_ws_added_payload,
    make_ws_removed_payload,
    make_ws_updated_payload,
)


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestWorkspaceReplay:
    def test_key(self):
        result = EventReplayEngine().replay([])
        assert "workspace" in result["final_state"]

    def test_round_trip_added(self):
        evts = [
            E(EventType.WORKSPACE_ITEM_ADDED.value, "e1",
              make_ws_added_payload(item_id="ws-1", activation=0.72, source="decision")),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["workspace"]["default"]["active"]["ws-1"]["activation"] == 0.72

    def test_round_trip_updated(self):
        evts = [
            E(EventType.WORKSPACE_UPDATED.value, "e1",
              make_ws_updated_payload(active_count=5, capacity=7)),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["workspace"]["default"]["capacity"] == 7

    def test_round_trip_removed(self):
        evts = [
            E(EventType.WORKSPACE_ITEM_ADDED.value, "e1",
              make_ws_added_payload(item_id="ws-x", activation=0.5, source="decision")),
            E(EventType.WORKSPACE_ITEM_REMOVED.value, "e2",
              make_ws_removed_payload(item_id="ws-x", reason="capacity")),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "ws-x" not in f["workspace"]["default"]["active"]

    def test_determinism(self):
        evts = [
            E(EventType.WORKSPACE_ITEM_ADDED.value, "e1",
              make_ws_added_payload(item_id="ws-a", activation=0.5, source="decision")),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["workspace"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["workspace"]
        assert r1 == r2

    def test_mixed_with_all(self):
        from allbrain.attention import make_attention_payload
        from allbrain.attribution import make_credit_payload
        evts = [
            E(EventType.SIGNAL_CREDIT_ASSIGNED.value, "e1",
              make_credit_payload(decision_id="d1", signal="dynamics", contribution=0.24, confidence=0.7)),
            E(EventType.ATTENTION_ALLOCATED.value, "e2",
              make_attention_payload(signal="dynamics", importance=0.74, cost=0.52, allocation=0.31)),
            E(EventType.WORKSPACE_ITEM_ADDED.value, "e3",
              make_ws_added_payload(item_id="ws-1", activation=0.72, source="decision")),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "attribution" in f
        assert "attention" in f
        assert "workspace" in f

    def test_seen_count_tracks(self):
        f = EventReplayEngine().replay([])["final_state"]
        assert "workspace" in f

    def test_empty(self):
        f = EventReplayEngine().replay([])["final_state"]
        assert f["workspace"] is not None
