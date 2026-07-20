"""Unit tests for fusion analyzer pure functions and FusionManager/DecisionManager.

Covers analyzer._pearson_correlation, compute_overlap_matrix,
detect_overlap_violations, _shared_event_lineage, overlap_violation_score,
plus FusionManager.query / known_keys and DecisionManager.query / known_keys
aggregation paths using SimpleNamespace event stubs.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from allbrain.domains.analysis.fusion.analyzer import (
    _pearson_correlation,
    _shared_event_lineage,
    compute_overlap_matrix,
    detect_overlap_violations,
    overlap_violation_score,
)
from allbrain.domains.analysis.fusion.manager import FusionManager
from allbrain.domains.reasoning.decision.manager import DecisionManager
from allbrain.events.schemas import EventType


def _evt(eid: str, etype: str, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(id=eid, type=etype, payload=payload)


# ---------------------------------------------------------------------------
# analyzer pure functions
# ---------------------------------------------------------------------------


class TestPearsonCorrelation:
    def test_too_few_samples_returns_zero(self):
        assert _pearson_correlation([0.5], [0.5]) == 0.0
        assert _pearson_correlation([], []) == 0.0

    def test_perfect_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0]
        y = [2.0, 4.0, 6.0, 8.0]
        assert abs(_pearson_correlation(x, y) - 1.0) < 1e-9

    def test_perfect_anticorrelation(self):
        x = [1.0, 2.0, 3.0, 4.0]
        y = [4.0, 3.0, 2.0, 1.0]
        assert abs(_pearson_correlation(x, y) - (-1.0)) < 1e-9

    def test_zero_variance_returns_zero(self):
        assert _pearson_correlation([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0


class TestComputeOverlapMatrix:
    def test_six_pairs_returned(self):
        m = compute_overlap_matrix([0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8])
        assert len(m) == 6
        assert ("capability", "learning") in m
        assert ("causal", "dynamics") not in m  # ordered pair only

    def test_empty_signals_zero_correlation(self):
        m = compute_overlap_matrix([], [], [], [])
        assert all(v == 0.0 for v in m.values())


class TestDetectOverlapViolations:
    def test_below_threshold_no_violation(self):
        m = {("capability", "learning"): 0.3}
        assert detect_overlap_violations(m, threshold=0.7) == set()

    def test_above_threshold_with_semantic_proxy(self):
        m = {("capability", "learning"): 0.8}
        v = detect_overlap_violations(m, threshold=0.7, semantic_proxy=0.5)
        assert ("capability", "learning") in v

    def test_above_threshold_no_semantic_below_margin(self):
        m = {("capability", "learning"): 0.75}
        v = detect_overlap_violations(m, threshold=0.7, semantic_proxy=0.0)
        assert v == set()

    def test_wide_margin_triggers_without_semantic(self):
        m = {("capability", "learning"): 0.9}
        v = detect_overlap_violations(m, threshold=0.7, semantic_proxy=0.0)
        assert ("capability", "learning") in v


class TestOverlapViolationScore:
    def test_direct_pair(self):
        assert overlap_violation_score({("a", "b")}, "a", "b") is True

    def test_reversed_pair(self):
        assert overlap_violation_score({("a", "b")}, "b", "a") is True

    def test_missing_pair(self):
        assert overlap_violation_score({("a", "b")}, "a", "c") is False


class TestSharedEventLineage:
    def test_no_matching_events_returns_zero(self):
        assert _shared_event_lineage("learning", "dynamics", []) == 0.0

    def test_disjoint_event_sets_return_zero_overlap(self):
        events = [
            _evt("e1", EventType.AGENT_CAPABILITY_LEARNED.value, {"agent_id": "a"}),
            _evt("e2", EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value, {"agent_id": "a"}),
        ]
        # eids_a and eids_b are disjoint -> 0 shared / 2 total = 0.0
        assert _shared_event_lineage("learning", "dynamics", events) == 0.0

    def test_non_dict_payload_ignored(self):
        events = [
            _evt("e1", EventType.AGENT_CAPABILITY_LEARNED.value, "not-a-dict"),
        ]
        assert _shared_event_lineage("learning", "dynamics", events) == 0.0


# ---------------------------------------------------------------------------
# FusionManager
# ---------------------------------------------------------------------------


class TestFusionManager:
    def test_query_empty_events(self):
        fm = FusionManager()
        out = fm.query([], agent_id="a", task_type="t")
        assert out["unified_score"] == 0.0
        assert out["signal_vector"]["capability"] == 0.0
        assert out["violations"] == []

    def test_query_aggregates_capability_and_learning(self):
        fm = FusionManager()
        events = [
            _evt(
                "e1",
                EventType.CAPABILITY_MATCHED.value,
                {"agent_id": "a", "task_type": "t", "match_score": 0.8},
            ),
            _evt(
                "e2",
                EventType.AGENT_CAPABILITY_LEARNED.value,
                {"agent_id": "a", "task_type": "t", "new_score": 0.6},
            ),
        ]
        out = fm.query(events, agent_id="a", task_type="t")
        assert out["calibrations"]["capability"] == 0.8
        assert out["calibrations"]["learning"] == 0.6

    def test_query_filters_other_agents(self):
        fm = FusionManager()
        events = [
            _evt(
                "e1",
                EventType.CAPABILITY_MATCHED.value,
                {"agent_id": "other", "task_type": "t", "match_score": 0.9},
            ),
        ]
        out = fm.query(events, agent_id="a", task_type="t")
        assert out["calibrations"]["capability"] == 0.0

    def test_query_dynamics_and_causal_channels(self):
        fm = FusionManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                {"agent_id": "a", "task_type": "t", "drift_score": 0.4},
            ),
            _evt(
                "e2",
                EventType.AGENT_COUNTERFACTUAL_RUN.value,
                {"agent_id": "a", "task_type": "t", "impact_score": 0.7},
            ),
        ]
        out = fm.query(events, agent_id="a", task_type="t")
        assert out["calibrations"]["dynamics"] == 0.4
        assert out["calibrations"]["causal"] == 0.7

    def test_query_non_dict_payload_ignored(self):
        fm = FusionManager()
        events = [
            SimpleNamespace(id="e1", type=EventType.CAPABILITY_MATCHED.value, payload="bad"),
        ]
        out = fm.query(events, agent_id="a", task_type="t")
        assert out["unified_score"] == 0.0

    def test_known_keys_extracts_agent_task_pairs(self):
        fm = FusionManager()
        events = [
            _evt("e1", "x", {"agent_id": "a", "task_type": "t"}),
            _evt("e2", "y", {"agent_id": "b", "task_type": "t"}),
            _evt("e3", "z", {"agent_id": "a"}),  # missing task_type -> skipped
            SimpleNamespace(id="e4", type="w", payload="nope"),
        ]
        keys = fm.known_keys(events)
        assert keys == {"a::t", "b::t"}

    def test_known_keys_empty_for_no_events(self):
        assert FusionManager().known_keys([]) == set()


# ---------------------------------------------------------------------------
# DecisionManager
# ---------------------------------------------------------------------------


class TestDecisionManager:
    def test_query_empty_events_returns_result(self):
        dm = DecisionManager()
        r = dm.query([], agent_id="a", task_type="t")
        assert 0.0 <= r.score <= 1.0

    def test_query_aggregates_telemetry(self):
        dm = DecisionManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_SELECTION_SCORED.value,
                {"agent_id": "a", "reputation": 0.8, "runtime_score": 0.7, "calibrated_trust": 0.6},
            ),
        ]
        r = dm.query(events, agent_id="a", task_type="t")
        assert 0.0 <= r.score <= 1.0

    def test_query_fusion_mode(self):
        dm = DecisionManager()
        events = [
            _evt(
                "e1",
                EventType.FUSION_COMPUTED.value,
                {
                    "agent_id": "a",
                    "capability": 0.8,
                    "learning": 0.7,
                    "dynamics": 0.5,
                    "causal": 0.6,
                    "unified_score": 0.65,
                },
            ),
        ]
        r = dm.query(events, agent_id="a", fusion=True)
        assert r.mode == "fusion"

    def test_query_filters_other_agents(self):
        dm = DecisionManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_SELECTION_SCORED.value,
                {"agent_id": "other", "reputation": 0.9, "runtime_score": 0.9, "calibrated_trust": 0.9},
            ),
        ]
        r = dm.query(events, agent_id="a", task_type="t")
        assert 0.0 <= r.score <= 1.0

    def test_query_capability_and_learning_channels(self):
        dm = DecisionManager()
        events = [
            _evt(
                "e1",
                EventType.CAPABILITY_MATCHED.value,
                {"agent_id": "a", "match_score": 0.9},
            ),
            _evt(
                "e2",
                EventType.AGENT_CAPABILITY_LEARNED.value,
                {"agent_id": "a", "new_score": 0.7},
            ),
        ]
        r = dm.query(events, agent_id="a", task_type="t")
        assert 0.0 <= r.score <= 1.0

    def test_query_dynamics_and_causal_channels(self):
        dm = DecisionManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                {"agent_id": "a", "drift_score": 0.3, "drift_level": "rising"},
            ),
            _evt(
                "e2",
                EventType.AGENT_CAUSAL_IMPACT_RECORDED.value,
                {"agent_id": "a", "impact_score": 0.5, "confidence": 0.8},
            ),
        ]
        r = dm.query(events, agent_id="a", task_type="t", dynamics=True)
        assert r.mode == "dynamic"

    def test_query_causal_mode(self):
        dm = DecisionManager()
        events = [
            _evt(
                "e1",
                EventType.AGENT_CAUSAL_IMPACT_RECORDED.value,
                {"agent_id": "a", "impact_score": 0.5, "confidence": 0.8},
            ),
        ]
        r = dm.query(events, agent_id="a", task_type="t", causal=True)
        assert r.mode == "causal"

    def test_known_keys_extracts_pairs(self):
        dm = DecisionManager()
        events = [
            _evt("e1", "x", {"agent_id": "a", "task_type": "t"}),
            _evt("e2", "y", {"agent_id": "b", "task_type": "t"}),
            _evt("e3", "z", {"agent_id": "a"}),  # missing task_type -> skipped
        ]
        keys = dm.known_keys(events)
        assert keys == {"a::t", "b::t"}

    def test_known_keys_empty_for_no_events(self):
        assert DecisionManager().known_keys([]) == set()

    def test_query_non_dict_payload_ignored(self):
        dm = DecisionManager()
        events = [
            SimpleNamespace(id="e1", type=EventType.AGENT_SELECTION_SCORED.value, payload="bad"),
        ]
        r = dm.query(events, agent_id="a", task_type="t")
        assert 0.0 <= r.score <= 1.0
