from __future__ import annotations

from allbrain.resilience.state_snapshot import StateSnapshotManager


class TestCreateSnapshot:
    def test_create_snapshot_returns_id(self) -> None:
        mgr = StateSnapshotManager()
        snap = mgr.create("test", {"key": "value"}, time=1)
        assert snap.snapshot_id.startswith("snap-")
        assert snap.component == "test"
        assert snap.state == {"key": "value"}
        assert snap.created_at == 1

    def test_create_with_metadata(self) -> None:
        mgr = StateSnapshotManager()
        snap = mgr.create("test", {"x": 1}, time=5, event_id="ev-42", pipeline_stage="routing")
        assert snap.event_id == "ev-42"
        assert snap.pipeline_stage == "routing"

    def test_snapshot_count(self) -> None:
        mgr = StateSnapshotManager()
        assert mgr.count == 0
        mgr.create("a", {})
        assert mgr.count == 1
        mgr.create("b", {})
        assert mgr.count == 2


class TestRestoreFromSnapshot:
    def test_restore_returns_state(self) -> None:
        mgr = StateSnapshotManager()
        snap = mgr.create("test", {"key": "value", "num": 42}, time=1)
        state = mgr.restore(snap.snapshot_id)
        assert state is not None
        assert state["key"] == "value"
        assert state["num"] == 42

    def test_restore_preserves_isolation(self) -> None:
        mgr = StateSnapshotManager()
        original = {"items": [1, 2, 3]}
        snap = mgr.create("test", original, time=1)
        state = mgr.restore(snap.snapshot_id)
        assert state is not None
        state["items"].append(4)
        # Original should not be mutated
        assert original["items"] == [1, 2, 3]


class TestRestoreNonexistent:
    def test_restore_unknown_returns_none(self) -> None:
        mgr = StateSnapshotManager()
        state = mgr.restore("nonexistent")
        assert state is None


class TestMultipleSnapshots:
    def test_multiple_components(self) -> None:
        mgr = StateSnapshotManager()
        s1 = mgr.create("comp-a", {"val": 1}, time=1)
        s2 = mgr.create("comp-b", {"val": 2}, time=2)
        assert mgr.restore(s1.snapshot_id) == {"val": 1}
        assert mgr.restore(s2.snapshot_id) == {"val": 2}

    def test_list_by_component(self) -> None:
        mgr = StateSnapshotManager()
        mgr.create("comp-a", {}, time=1)
        mgr.create("comp-b", {}, time=2)
        mgr.create("comp-a", {}, time=3)
        a_snaps = mgr.list_snapshots("comp-a")
        assert len(a_snaps) == 2
        b_snaps = mgr.list_snapshots("comp-b")
        assert len(b_snaps) == 1


class TestDeleteAfterRestore:
    def test_delete_removes_snapshot(self) -> None:
        mgr = StateSnapshotManager()
        snap = mgr.create("test", {"x": 1}, time=1)
        assert mgr.count == 1
        deleted = mgr.delete(snap.snapshot_id)
        assert deleted
        assert mgr.count == 0
        assert mgr.restore(snap.snapshot_id) is None

    def test_delete_nonexistent(self) -> None:
        mgr = StateSnapshotManager()
        assert not mgr.delete("nonexistent")

    def test_clear_all(self) -> None:
        mgr = StateSnapshotManager()
        mgr.create("a", {}, time=1)
        mgr.create("b", {}, time=2)
        assert mgr.count == 2
        mgr.clear()
        assert mgr.count == 0
