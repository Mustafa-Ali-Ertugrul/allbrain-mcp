from __future__ import annotations

import pytest

from allbrain.capabilities.events import (
    make_classified_payload,
    make_matched_payload,
    make_registered_payload,
    validate_registered,
)
from allbrain.capabilities.scorer import (
    match_kind,
    match_score,
    normalize_task_type,
)


class TestNormalize:
    def test_normalize(self):
        assert normalize_task_type("Python_Debugging") == "pythondebugging"
        assert normalize_task_type("python-debugging") == "pythondebugging"
        assert normalize_task_type("PythonDebugging") == "pythondebugging"


class TestMatch:
    def test_exact(self):
        assert match_kind("python", "python") == "exact"

    def test_partial(self):
        assert match_kind("debugging", "python_debugging") == "partial"

    def test_none(self):
        assert match_kind("rust", "python") == "none"


class TestMatchScore:
    def test_exact_match(self):
        ms, mk = match_score(agent_capabilities=[("python", 1.0)], task_type="python")
        assert ms == pytest.approx(1.0)
        assert mk == "exact"

    def test_partial_match(self):
        ms, mk = match_score(agent_capabilities=[("python", 0.5)], task_type="python_debugging")
        assert ms == pytest.approx(0.25)
        assert mk == "partial"

    def test_no_match(self):
        ms, mk = match_score(agent_capabilities=[], task_type="python")
        assert ms == 0.0
        assert mk == "none"

    def test_weighted(self):
        ac = [("python", 1.0), ("debugging", 0.5)]
        ms, mk = match_score(agent_capabilities=ac, task_type="python")
        assert mk == "exact"


class TestPayloads:
    def test_registered(self):
        p = make_registered_payload(agent_id="a", capability="python", weight=0.8)
        assert p["agent_id"] == "a"
        assert p["weight"] == 0.8

    def test_classified(self):
        p = make_classified_payload(task_id="t", task_type="python")
        assert p["task_type"] == "python"

    def test_matched(self):
        p = make_matched_payload(agent_id="a", task_type="python", match_score=0.5, match_kind="partial")
        assert p["match_kind"] == "partial"


class TestValidation:
    def test_registered_rejects(self):
        with pytest.raises(ValueError):
            make_registered_payload(agent_id="", capability="x", weight=0.5)
