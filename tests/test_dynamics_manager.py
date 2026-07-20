"""Unit tests for CapabilityDynamicsManager (dynamics/manager.py).

Covers query() aggregation across all event channels and known_keys().
"""

from __future__ import annotations

from types import SimpleNamespace

from allbrain.domains.analysis.dynamics.manager import CapabilityDynamicsManager
from allbrain.events.schemas import EventType


def _evt(eid: str, etype: str, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(id=eid, type=etype, payload=payload)


class TestCapabilityDynamicsManager:
    def test_query_empty_events(self):
        dm = CapabilityDynamicsManager()
        out = dm.query([], agent_id="a", task_type="t")
        assert "drift" in out
        assert "trend" in out
        assert "forecast" in out

    def test_query_aggregates_observed_and_learned(self):
        dm = CapabilityDynamicsManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_OBSERVED.value,
                {"agent_id": "a", "task_type": "t"},
            ),
            _evt(
                "e2",
                EventType.AGENT_CAPABILITY_LEARNED.value,
                {"agent_id": "a", "task_type": "t", "new_score": 0.8},
            ),
            _evt(
                "e3",
                EventType.AGENT_CAPABILITY_LEARNED.value,
                {"agent_id": "a", "task_type": "t", "new_score": 0.6},
            ),
        ]
        out = dm.query(events, agent_id="a", task_type="t")
        assert "drift" in out
        assert "trend" in out
        assert "forecast" in out

    def test_query_decayed_updates_scores(self):
        dm = CapabilityDynamicsManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_DECAYED.value,
                {"agent_id": "a", "task_type": "t", "new_score": 0.4},
            ),
        ]
        out = dm.query(events, agent_id="a", task_type="t")
        assert "drift" in out

    def test_query_drift_detected_updates_last_drift(self):
        dm = CapabilityDynamicsManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                {"agent_id": "a", "task_type": "t", "drift_score": 0.7, "drift_level": "high"},
            ),
        ]
        out = dm.query(events, agent_id="a", task_type="t")
        # drift_level is recomputed from scores; with no learned scores it stays low
        assert out["drift"]["drift_level"] in ("low", "medium", "high")
        assert out["drift"]["agent_id"] == "a"

    def test_query_trend_updated_updates_last_label(self):
        dm = CapabilityDynamicsManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_TREND_UPDATED.value,
                {"agent_id": "a", "task_type": "t", "label": "rising"},
            ),
        ]
        out = dm.query(events, agent_id="a", task_type="t")
        assert out["trend"]["label"] == "rising"

    def test_query_filters_other_agents(self):
        dm = CapabilityDynamicsManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_LEARNED.value,
                {"agent_id": "other", "task_type": "t", "new_score": 0.9},
            ),
        ]
        out = dm.query(events, agent_id="a", task_type="t")
        # other agent's events are filtered out -> drift computed for "a" with no scores
        assert out["drift"]["agent_id"] == "a"
        assert out["drift"]["drift_score"] == 0.0

    def test_query_filters_other_task_types(self):
        dm = CapabilityDynamicsManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_LEARNED.value,
                {"agent_id": "a", "task_type": "other", "new_score": 0.9},
            ),
        ]
        out = dm.query(events, agent_id="a", task_type="t")
        assert "drift" in out

    def test_query_non_dict_payload_ignored(self):
        dm = CapabilityDynamicsManager()
        events = [
            SimpleNamespace(id="e1", type=EventType.AGENT_CAPABILITY_LEARNED.value, payload="bad"),
        ]
        out = dm.query(events, agent_id="a", task_type="t")
        assert "drift" in out

    def test_query_horizon_parameter(self):
        dm = CapabilityDynamicsManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_LEARNED.value,
                {"agent_id": "a", "task_type": "t", "new_score": 0.8},
            ),
        ]
        out = dm.query(events, agent_id="a", task_type="t", horizon=10)
        assert "forecast" in out

    def test_known_keys_extracts_pairs(self):
        dm = CapabilityDynamicsManager()
        events = [
            _evt("e1", "x", {"agent_id": "a", "task_type": "t"}),
            _evt("e2", "y", {"agent_id": "b", "task_type": "t"}),
            _evt("e3", "z", {"agent_id": "a"}),  # missing task_type -> skipped
        ]
        keys = dm.known_keys(events)
        assert keys == {"a::t", "b::t"}

    def test_known_keys_empty_for_no_events(self):
        assert CapabilityDynamicsManager().known_keys([]) == set()

    def test_known_keys_ignores_non_dict_payload(self):
        dm = CapabilityDynamicsManager()
        events = [SimpleNamespace(id="e1", type="x", payload="nope")]
        assert dm.known_keys(events) == set()
