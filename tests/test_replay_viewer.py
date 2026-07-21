"""Tests for ui/replay_viewer.py - _diff_highlights."""

from allbrain.domains.memory.ui.replay_viewer import _diff_highlights


class TestDiffHighlights:
    def test_none_diff(self):
        assert _diff_highlights(None) == []

    def test_empty_diff(self):
        assert _diff_highlights({}) == []

    def test_status_delta(self):
        diff = {"status_delta": {"task1": {"left": "pending", "right": "completed"}}}
        highlights = _diff_highlights(diff)
        assert len(highlights) == 1
        assert highlights[0]["kind"] == "status"
        assert highlights[0]["task_id"] == "task1"

    def test_decision_delta(self):
        diff = {"decision_delta": {"changed": True, "left_count": 1, "right_count": 2}}
        highlights = _diff_highlights(diff)
        assert len(highlights) == 1
        assert highlights[0]["kind"] == "decision"
        assert highlights[0]["left_count"] == 1

    def test_failure_delta(self):
        diff = {"failure_delta": {"changed": True, "left_count": 0, "right_count": 1}}
        highlights = _diff_highlights(diff)
        assert len(highlights) == 1
        assert highlights[0]["kind"] == "failure"

    def test_both_deltas(self):
        diff = {
            "status_delta": {"t1": {"left": "a", "right": "b"}},
            "decision_delta": {"changed": True, "left_count": 1, "right_count": 2},
        }
        highlights = _diff_highlights(diff)
        assert len(highlights) == 2

    def test_unchanged_delta_skipped(self):
        diff = {"decision_delta": {"changed": False}}
        assert _diff_highlights(diff) == []
