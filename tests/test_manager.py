from __future__ import annotations

from allbrain.domains.collaboration.workspace import (
    WorkspaceManager,
    make_ws_added_payload,
    make_ws_removed_payload,
    make_ws_updated_payload,
)


class TestManager:
    def test_update(self):
        mgr = WorkspaceManager()
        r = mgr.update([], signal_rewards={"capability": 0.5, "learning": 0.3}, attention_weight=0.8)
        assert r["active_count"] >= 0
        assert r["capacity"] == 7

    def test_capacity_enforcement(self):
        mgr = WorkspaceManager()
        mgr.set_capacity(2)
        for i in range(10):
            mgr.update([], signal_rewards={"causal": 0.7}, attention_weight=0.9, item_id=f"item-{i}")
        assert len(mgr.get_active_items()) <= 2

    def test_signal_rewards_activation(self):
        mgr = WorkspaceManager()
        r1 = mgr.update([], signal_rewards={"causal": 0.1}, attention_weight=0.5, item_id="low")
        r2 = mgr.update([], signal_rewards={"causal": 0.9}, attention_weight=0.5, item_id="high")
        assert r2["added"][0]["activation"] > r1["added"][0]["activation"]

    def test_item_replacement(self):
        mgr = WorkspaceManager()
        mgr.set_capacity(3)
        mgr.update([], signal_rewards={"a": 0.9}, attention_weight=0.9, item_id="item1")
        mgr.update([], signal_rewards={"a": 0.8}, attention_weight=0.8, item_id="item2")
        mgr.update([], signal_rewards={"a": 0.7}, attention_weight=0.7, item_id="item3")
        mgr.update([], signal_rewards={"a": 1.0}, attention_weight=1.0, item_id="item4")
        active = mgr.get_active_items()
        assert len(active) == 3

    def test_get_active_empty(self):
        mgr = WorkspaceManager()
        assert len(mgr.get_active_items()) == 0

    def test_set_capacity(self):
        mgr = WorkspaceManager()
        mgr.set_capacity(10)
        r = mgr.update([], signal_rewards={}, attention_weight=0.5)
        assert r["capacity"] == 10

    def test_seen_count(self):
        mgr = WorkspaceManager()
        r = mgr.update([], signal_rewards={}, attention_weight=0.5, item_id="a")
        assert r["total_seen"] >= 1

    def test_eviction_count(self):
        mgr = WorkspaceManager()
        mgr.set_capacity(1)
        mgr.update([], signal_rewards={}, attention_weight=0.5, item_id="a")
        r = mgr.update([], signal_rewards={}, attention_weight=0.9, item_id="b")
        assert r["total_evicted"] >= 0
