from __future__ import annotations

import pytest

from allbrain.meta_scoring import ProfileStore, ScoringProfile
from allbrain.meta_scoring.model import META_SCORING_WEIGHT_MIN, META_SCORING_WEIGHT_MAX


class TestProfileLearning:
    def test_profile_updates_in_expected_direction(self):
        store = ProfileStore()
        original = store.get("overload")
        assert original.success_weight == 0.50

        # Simulate learning: increase success weight
        store.set(ScoringProfile("overload", success_weight=0.55))
        updated = store.get("overload")
        assert updated.success_weight > original.success_weight
        assert updated.version > original.version

    def test_weights_clamped_low(self):
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=-0.5))
        p = store.get("timeout")
        assert p.success_weight >= META_SCORING_WEIGHT_MIN

    def test_weights_clamped_high(self):
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=2.0))
        p = store.get("timeout")
        assert p.success_weight <= META_SCORING_WEIGHT_MAX

    def test_exploration_bonus_clamped(self):
        store = ProfileStore()
        store.set(ScoringProfile("timeout", exploration_bonus=0.5))
        p = store.get("timeout")
        assert p.exploration_bonus <= 0.30

    def test_exploration_bonus_clamped_low(self):
        store = ProfileStore()
        store.set(ScoringProfile("timeout", exploration_bonus=-0.1))
        p = store.get("timeout")
        assert p.exploration_bonus >= 0.0

    def test_multiple_updates_increment_version(self):
        store = ProfileStore()
        for i in range(5):
            store.set(ScoringProfile("timeout", success_weight=0.30 + i * 0.05))
        v = store.get("timeout")
        assert v.version == 5

    def test_independent_fault_types_dont_interfere(self):
        store = ProfileStore()
        store.set(ScoringProfile("timeout", success_weight=0.30))
        store.set(ScoringProfile("overload", success_weight=0.60))
        assert store.get("timeout").success_weight == 0.30
        assert store.get("overload").success_weight == 0.60

    def test_default_profile_is_fallback(self):
        store = ProfileStore()
        p1 = store.get("latency")
        assert p1.success_weight == 0.50
        assert p1.version == 0