from __future__ import annotations

import pytest

from allbrain.domains.learning.meta_scoring import (
    META_SCORING_OVERRIDE_CONFIDENCE,
    MetaScorer,
    MetaScoreResult,
    MetaScoringReducer,
    ProfileStore,
    ScoringProfile,
    make_scoring_profile_updated_payload,
    validate_scoring_profile_updated,
)
from allbrain.events.schemas import EventType


class TestMetaScorer:
    def test_default_profile_matches_sprint72_weights(self):
        store = ProfileStore()
        profile = store.get("timeout")
        assert profile.success_weight == 0.50
        assert profile.risk_weight == 0.20
        assert profile.stability_weight == 0.20
        assert profile.drift_weight == 0.10
        assert profile.exploration_bonus == 0.0

    def test_meta_score_matches_static_when_same_weights(self):
        store = ProfileStore()
        scorer = MetaScorer(store)
        result = scorer.score(
            "timeout",
            0.38,
            success_rate=0.8,
            risk_estimate=0.4,
            stability_estimate=0.6,
            drift_estimate=0.2,
        )
        assert result.static_score == 0.38
        assert abs(result.meta_score - 0.38) < 1e-6

    def test_no_override_when_gap_below_threshold(self):
        store = ProfileStore()
        scorer = MetaScorer(store)
        result = scorer.score(
            "timeout",
            0.42,
            success_rate=0.8,
            risk_estimate=0.4,
            stability_estimate=0.6,
            drift_estimate=0.2,
        )
        assert not result.override_applied
        assert result.confidence < 1.0

    def test_override_applied_when_gap_large(self):
        store = ProfileStore()
        store.set(
            ScoringProfile(
                "timeout",
                success_weight=0.05,
                risk_weight=0.70,
                stability_weight=0.05,
                drift_weight=0.05,
            )
        )
        scorer = MetaScorer(store)
        result = scorer.score(
            "timeout",
            0.42,
            success_rate=0.8,
            risk_estimate=0.4,
            stability_estimate=0.6,
            drift_estimate=0.2,
        )
        assert result.override_applied
        assert result.blended_score != result.static_score

    def test_per_fault_type_profiles(self):
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=0.10))
        store.set(ScoringProfile("overload", success_weight=0.60))
        scorer = MetaScorer(store)
        r_timeout = scorer.score(
            "timeout", 0.5, success_rate=1.0, risk_estimate=0.5, stability_estimate=0.5, drift_estimate=0.0
        )
        r_overload = scorer.score(
            "overload", 0.5, success_rate=1.0, risk_estimate=0.5, stability_estimate=0.5, drift_estimate=0.0
        )
        assert r_timeout.meta_score != r_overload.meta_score

    def test_exploration_bonus_adds_to_score(self):
        store = ProfileStore()
        store.set(ScoringProfile("latency", exploration_bonus=0.15))
        scorer = MetaScorer(store)
        result = scorer.score(
            "latency", 0.4, success_rate=0.6, risk_estimate=0.5, stability_estimate=0.5, drift_estimate=0.3
        )
        meta_no_bonus = 0.6 * 0.5 - (1 - 0.5) * 0.2 + 0.5 * 0.2 - 0.3 * 0.1
        assert result.meta_score == meta_no_bonus + 0.15

    def test_version_increments_on_set(self):
        store = ProfileStore()
        p1 = store.get("timeout")
        assert p1.version == 0
        store.set(ScoringProfile("timeout", success_weight=0.30))
        p2 = store.get("timeout")
        assert p2.version == 1
        assert p2.success_weight == 0.30


class TestProfileStore:
    def test_get_missing_returns_default(self):
        store = ProfileStore()
        p = store.get("nonexistent")
        assert p.fault_type == "nonexistent"
        assert p.success_weight == 0.50
        assert p.version == 0

    def test_all_profiles_serializable(self):
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=0.30))
        all_profs = store.all_profiles()
        assert "timeout" in all_profs
        assert all_profs["timeout"]["success_weight"] == 0.30


class TestMetaScoringEvents:
    def test_valid_payload(self):
        p = make_scoring_profile_updated_payload(
            fault_type="timeout",
            success_weight=0.50,
            risk_weight=0.20,
            stability_weight=0.20,
            drift_weight=0.10,
            exploration_bonus=0.0,
            version=1,
        )
        validate_scoring_profile_updated(p)

    def test_invalid_missing_key(self):
        with pytest.raises(ValueError, match="missing"):
            validate_scoring_profile_updated({"fault_type": "timeout"})

    def test_weights_clamped_in_payload(self):
        with pytest.raises(ValueError):
            make_scoring_profile_updated_payload(
                fault_type="timeout",
                success_weight=1.5,
                risk_weight=0.20,
                stability_weight=0.20,
                drift_weight=0.10,
                exploration_bonus=0.0,
                version=1,
            )


class TestMetaScoringReducer:
    def test_tracks_profile_updates(self):
        reducer = MetaScoringReducer()
        event = _make_event(
            EventType.SCORING_PROFILE_UPDATED.value,
            {
                "fault_type": "timeout",
                "success_weight": 0.30,
                "risk_weight": 0.20,
                "stability_weight": 0.25,
                "drift_weight": 0.15,
                "exploration_bonus": 0.05,
                "version": 1,
            },
        )
        reducer.apply(event)
        snap = reducer.all_snapshots()
        assert snap["default"]["total_updates"] == 1
        assert "timeout" in snap["default"]["profiles"]

    def test_ignores_unknown_events(self):
        reducer = MetaScoringReducer()
        reducer.apply(_make_event("unknown", {}))
        assert reducer.all_snapshots()["default"]["total_updates"] == 0


def _make_event(type_str: str, payload: dict):
    import types

    ev = types.SimpleNamespace()
    ev.id = f"test_{type_str}_{hash(str(payload))}"
    ev.type = type_str
    ev.payload = payload
    ev.created_at = None
    ev.agent_id = None
    ev.session_id = None
    return ev
