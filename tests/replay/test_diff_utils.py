"""Tests for replay/diff_utils.py."""

from allbrain.domains.memory.replay.diff_utils import _dict_delta, _list_delta, _task_statuses


class TestTaskStatuses:
    def test_empty(self):
        assert _task_statuses({"tasks": {}}) == {}

    def test_multiple_tasks(self):
        s = {"tasks": {"t1": {"status": "completed"}, "t2": {"status": "started"}}}
        assert _task_statuses(s) == {"t1": "completed", "t2": "started"}

    def test_default_status(self):
        assert _task_statuses({"tasks": {"t1": {}}}) == {"t1": "unknown"}


class TestDictDelta:
    def test_no_delta(self):
        assert _dict_delta({"a": 1}, {"a": 1}) == {}

    def test_delta_found(self):
        assert _dict_delta({"a": 1}, {"a": 2}) == {"a": {"left": 1, "right": 2}}

    def test_key_added(self):
        d = _dict_delta({"a": 1}, {"a": 1, "b": 2})
        assert "b" in d

    def test_key_removed(self):
        d = _dict_delta({"a": 1, "b": 2}, {"a": 1})
        assert "b" in d


class TestListDelta:
    def test_equal(self):
        r = _list_delta([{"id": 1}], [{"id": 1}])
        assert r == {"left_count": 1, "right_count": 1, "changed": False}

    def test_different(self):
        assert _list_delta([{"id": 1}], [{"id": 2}])["changed"] is True

    def test_different_counts(self):
        r = _list_delta([{"id": 1}], [{"id": 1}, {"id": 2}])
        assert r["changed"] is True and r["left_count"] == 1 and r["right_count"] == 2
