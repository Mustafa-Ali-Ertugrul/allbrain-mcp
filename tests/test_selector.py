from __future__ import annotations

from allbrain.workspace import MIN_ACTIVATION, WorkspaceItem, select_workspace_items


class TestSelector:
    def test_ordering(self):
        items = [WorkspaceItem("1", "d", 0.5, 100), WorkspaceItem("2", "d", 0.9, 200), WorkspaceItem("3", "d", 0.3, 300)]
        selected = select_workspace_items(items, 5)
        assert selected[0].item_id == "2"

    def test_capacity_limit(self):
        items = [WorkspaceItem(str(i), "d", 0.5, i) for i in range(10)]
        selected = select_workspace_items(items, 3)
        assert len(selected) == 3

    def test_tie_newest(self):
        items = [WorkspaceItem("a", "d", 0.5, 100), WorkspaceItem("b", "d", 0.5, 200)]
        selected = select_workspace_items(items, 5)
        assert selected[0].item_id == "b"

    def test_min_activation_filter(self):
        items = [WorkspaceItem("1", "d", 0.05, 1), WorkspaceItem("2", "d", 0.5, 2)]
        selected = select_workspace_items(items, 5)
        assert len(selected) == 1
        assert selected[0].item_id == "2"

    def test_empty(self):
        selected = select_workspace_items([], 5)
        assert selected == []

    def test_mixed_activations(self):
        items = [
            WorkspaceItem("a", "d", 0.9, 5), WorkspaceItem("b", "d", 0.7, 4),
            WorkspaceItem("c", "d", 0.8, 3), WorkspaceItem("d", "d", 0.6, 2),
        ]
        selected = select_workspace_items(items, 5)
        assert [s.item_id for s in selected] == ["a", "c", "b", "d"]

    def test_exact_capacity(self):
        items = [WorkspaceItem(str(i), "d", 0.5, i) for i in range(5)]
        selected = select_workspace_items(items, 5)
        assert len(selected) == 5

    def test_no_cost_field(self):
        item = WorkspaceItem("x", "d", 0.5, 100)
        assert not hasattr(item, "cost")
