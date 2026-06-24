from __future__ import annotations

import pytest

from allbrain.policy_routing import (
    FamilySelector,
    MetaPolicyRouter,
    FamilyType,
    DEFAULT_FAMILY_MAP,
    RoutingDecision,
)


class TestFamilySelector:
    def test_timeout_maps_to_throttle(self):
        selector = FamilySelector()
        decision = selector.select("timeout", "retry_spike")
        assert decision.family.name == FamilyType.THROTTLE

    def test_connection_maps_to_throttle(self):
        selector = FamilySelector()
        decision = selector.select("connection", "circuit_open")
        assert decision.family.name == FamilyType.THROTTLE

    def test_overload_maps_to_warmup(self):
        selector = FamilySelector()
        decision = selector.select("overload", "latency_rise")
        assert decision.family.name == FamilyType.WARMUP

    def test_drift_maps_to_snapshot(self):
        selector = FamilySelector()
        decision = selector.select("drift", "pattern_shift")
        assert decision.family.name == FamilyType.SNAPSHOT

    def test_unknown_fault_falls_back_to_snapshot(self):
        selector = FamilySelector()
        decision = selector.select("unknown_fault_type", "weird_signal")
        assert decision.family.name == FamilyType.SNAPSHOT

    def test_confidence_higher_for_direct_match(self):
        selector = FamilySelector()
        d1 = selector.select("timeout", "retry_spike")
        d2 = selector.select("unknown", "retry_spike")
        assert d1.confidence > d2.confidence


class TestMetaPolicyRouter:
    def test_router_filters_to_family_strategies(self):
        router = MetaPolicyRouter()
        all_candidates = ["throttle_retry", "rate_limit", "log_warning", "pre_rollback_snapshot"]
        decision, allowed = router.route("timeout", "retry_spike", all_candidates)
        assert "throttle_retry" in allowed
        assert "rate_limit" in allowed
        assert "log_warning" not in allowed

    def test_empty_allowed_falls_back_to_full_family(self):
        router = MetaPolicyRouter()
        all_candidates = ["log_warning", "pre_rollback_snapshot"]
        decision, allowed = router.route("timeout", "retry_spike", all_candidates)
        # THROTTLE family = throttle_retry, rate_limit
        assert "throttle_retry" in allowed
        assert "rate_limit" in allowed

    def test_router_returns_routing_decision(self):
        router = MetaPolicyRouter()
        decision, allowed = router.route("overload", "latency_rise", [])
        assert isinstance(decision, RoutingDecision)
        assert decision.fault_type == "overload"
        assert decision.signal_type == "latency_rise"

    def test_all_default_families_have_strategies(self):
        from allbrain.policy_routing.model import FAMILY_STRATEGIES
        for ft in FamilyType:
            assert ft in FAMILY_STRATEGIES
            assert len(FAMILY_STRATEGIES[ft]) > 0

    def test_default_family_map_covers_expected_types(self):
        expected = {"timeout", "retry_spike", "connection", "circuit_open",
                     "latency_rise", "overload", "failure", "drift", "pattern"}
        for key in expected:
            assert key in DEFAULT_FAMILY_MAP, f"Missing mapping for {key}"

    def test_to_event_payload(self):
        router = MetaPolicyRouter()
        decision, _ = router.route("timeout", "retry_spike", [])
        payload = router.to_event_payload(decision)
        assert payload["family"] == "throttle"
        assert "strategies" in payload
        assert payload["fault_type"] == "timeout"
        assert 0.0 <= payload["confidence"] <= 1.0
