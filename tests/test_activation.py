from __future__ import annotations

from allbrain.workspace import compute_activation, apply_decay, WorkspaceItem, DECAY_RATE
import math


class TestActivation:
    def test_basic(self):
        a = compute_activation(attention_weight=0.5, reward=0.8, age=0)
        assert abs(a - 0.4) < 1e-9

    def test_recency_decay(self):
        a0 = compute_activation(attention_weight=0.5, reward=0.8, age=0)
        a10 = compute_activation(attention_weight=0.5, reward=0.8, age=10)
        assert a10 < a0

    def test_reward_effect(self):
        a_low = compute_activation(attention_weight=0.5, reward=0.1, age=0)
        a_high = compute_activation(attention_weight=0.5, reward=0.9, age=0)
        assert a_high > a_low

    def test_attention_effect(self):
        a_low = compute_activation(attention_weight=0.1, reward=0.5, age=0)
        a_high = compute_activation(attention_weight=0.9, reward=0.5, age=0)
        assert a_high > a_low

    def test_age_zero(self):
        a = compute_activation(attention_weight=1.0, reward=1.0, age=0)
        assert abs(a - 1.0) < 1e-9

    def test_exp_decay_math(self):
        a5 = compute_activation(attention_weight=1.0, reward=1.0, age=5)
        expected = math.exp(-5.0 * DECAY_RATE)
        assert abs(a5 - expected) < 1e-9

    def test_decay_zeroes(self):
        items = [WorkspaceItem(item_id="x", source="d", activation=0.5, timestamp=0)]
        decayed = apply_decay(items, 100)
        assert decayed[0].activation < 0.01

    def test_zero_input(self):
        a = compute_activation(attention_weight=0.0, reward=0.0, age=0)
        assert a == 0.0