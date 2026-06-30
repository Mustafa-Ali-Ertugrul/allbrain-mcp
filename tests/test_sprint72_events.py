from __future__ import annotations

import pytest

from allbrain.policy_competition.events import (
    make_competition_held_payload,
    validate_competition_held,
)
from allbrain.policy_competition.reducer import PolicyCompetitionReducer
from allbrain.policy_routing.events import (
    make_family_candidate_evaluated_payload,
    make_policy_family_selected_payload,
    validate_family_candidate_evaluated,
    validate_policy_family_selected,
)
from allbrain.policy_routing.reducer import PolicyRoutingReducer
from allbrain.soft_repair.events import (
    make_policy_blended_payload,
    validate_policy_blended,
)
from allbrain.soft_repair.reducer import SoftRepairReducer


class TestSprint72EventValidation:
    def test_policy_family_selected_valid(self):
        p = make_policy_family_selected_payload(
            family="throttle",
            strategies=["throttle_retry", "rate_limit"],
            fault_type="timeout",
            signal_type="retry_spike",
            confidence=0.85,
        )
        validate_policy_family_selected(p)

    def test_policy_family_selected_invalid_missing_key(self):
        with pytest.raises(ValueError, match="missing"):
            validate_policy_family_selected({"family": "throttle"})

    def test_family_candidate_evaluated_valid(self):
        p = make_family_candidate_evaluated_payload(
            candidate_id="cand_1",
            fault_type="timeout",
            strategy="rate_limit",
            score=0.65,
            success_rate=0.8,
            risk_penalty=0.2,
            stability_bonus=0.5,
            drift_penalty=0.1,
        )
        validate_family_candidate_evaluated(p)

    def test_competition_held_valid(self):
        p = make_competition_held_payload(
            fault_type="timeout",
            winner_policy_id="p1",
            winner_strategy="rate_limit",
            winner_score=0.72,
            confidence=0.3,
            candidate_count=3,
        )
        validate_competition_held(p)

    def test_competition_held_invalid_score_range(self):
        with pytest.raises(ValueError):
            make_competition_held_payload(
                fault_type="timeout",
                winner_policy_id="p1",
                winner_strategy="rate_limit",
                winner_score=5.0,
                confidence=0.3,
                candidate_count=3,
            )

    def test_policy_blended_valid(self):
        p = make_policy_blended_payload(
            old_policy_id="v1",
            new_policy_id="v2",
            fault_type="timeout",
            old_weight=0.6,
            new_weight=0.4,
            stability_score=0.55,
        )
        validate_policy_blended(p)

    def test_policy_blended_invalid_weight(self):
        with pytest.raises(ValueError):
            make_policy_blended_payload(
                old_policy_id="v1",
                new_policy_id="v2",
                fault_type="timeout",
                old_weight=1.5,
                new_weight=0.4,
                stability_score=0.55,
            )

    def test_family_candidate_evaluated_invalid_score(self):
        with pytest.raises(ValueError):
            make_family_candidate_evaluated_payload(
                candidate_id="cand_1",
                fault_type="timeout",
                strategy="rate_limit",
                score=3.0,
                success_rate=0.8,
                risk_penalty=0.2,
                stability_bonus=0.5,
                drift_penalty=0.1,
            )


class TestSprint72Reducers:
    def test_policy_routing_reducer_tracks_selections(self):
        reducer = PolicyRoutingReducer()
        event = _make_event("policy_family_selected", {
            "family": "throttle", "strategies": ["retry"],
            "fault_type": "timeout", "signal_type": "retry",
            "confidence": 0.85,
        })
        reducer.apply(event)
        snap = reducer.all_snapshots()
        assert snap["default"]["total_selections"] == 1

    def test_policy_competition_reducer_tracks_competitions(self):
        reducer = PolicyCompetitionReducer()
        event = _make_event("competition_held", {
            "fault_type": "timeout", "winner_policy_id": "p1",
            "winner_strategy": "retry", "winner_score": 0.7,
            "confidence": 0.3, "candidate_count": 2,
        })
        reducer.apply(event)
        snap = reducer.all_snapshots()
        assert snap["default"]["total_competitions"] == 1

    def test_soft_repair_reducer_tracks_blends(self):
        reducer = SoftRepairReducer()
        event = _make_event("policy_blended", {
            "old_policy_id": "v1", "new_policy_id": "v2",
            "fault_type": "timeout", "old_weight": 0.6,
            "new_weight": 0.4, "stability_score": 0.55,
        })
        reducer.apply(event)
        snap = reducer.all_snapshots()
        assert snap["default"]["total_blends"] == 1

    def test_reducers_ignore_unknown_events(self):
        pr = PolicyRoutingReducer()
        pc = PolicyCompetitionReducer()
        sr = SoftRepairReducer()
        ev = _make_event("unknown_type", {})
        pr.apply(ev)
        pc.apply(ev)
        sr.apply(ev)
        assert pr.all_snapshots()["default"]["total_selections"] == 0
        assert pc.all_snapshots()["default"]["total_competitions"] == 0
        assert sr.all_snapshots()["default"]["total_blends"] == 0


def _make_event(type_str: str, payload: dict):
    """Minimal event stub for reducer tests."""
    import types
    ev = types.SimpleNamespace()
    ev.id = f"test_{type_str}_{hash(str(payload))}"
    ev.type = type_str
    ev.payload = payload
    ev.created_at = None
    ev.agent_id = None
    ev.session_id = None
    return ev
