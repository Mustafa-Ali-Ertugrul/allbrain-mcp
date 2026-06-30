from __future__ import annotations

import math

import pytest

from allbrain.learning_safety.entropy import (
    EntropyCalculator,
    entropy_decay,
    shannon_entropy,
)
from allbrain.learning_safety.model import DEFAULT_BASE_EPSILON, DEFAULT_DECAY_RATE


class TestEntropy:
    def setup_method(self):
        self.calc = EntropyCalculator()

    def test_shannon_entropy_uniform(self):
        # Uniform distribution of 4 → H = log(4) ≈ 1.386
        assert shannon_entropy([0.25, 0.25, 0.25, 0.25]) == pytest.approx(math.log(4))

    def test_shannon_entropy_deterministic(self):
        # All weight on one strategy → H = 0
        assert shannon_entropy([1.0, 0.0, 0.0]) == 0.0

    def test_shannon_entropy_handles_zeros(self):
        assert shannon_entropy([0.0, 0.0, 1.0]) == 0.0

    def test_shannon_entropy_empty(self):
        assert shannon_entropy([]) == 0.0

    def test_entropy_decay_formula(self):
        eps0 = 0.10
        decay = 0.95
        assert entropy_decay(eps0, decay, 0) == pytest.approx(0.10)
        assert entropy_decay(eps0, decay, 1) == pytest.approx(0.095)
        assert entropy_decay(eps0, decay, 10) == pytest.approx(0.10 * 0.95 ** 10)

    def test_calculator_current_epsilon(self):
        calc = EntropyCalculator(base_epsilon=0.20, decay_rate=0.90)
        assert calc.current_epsilon() == pytest.approx(0.20)
        calc.advance()
        assert calc.current_epsilon() == pytest.approx(0.18)

    def test_calculator_advance(self):
        calc = EntropyCalculator()
        assert calc.cycle_count == 0
        calc.advance()
        calc.advance()
        assert calc.cycle_count == 2

    def test_from_strategy_counts(self):
        state = EntropyCalculator.from_strategy_counts({"A": 1, "B": 1, "C": 1, "D": 1})
        assert state.n_strategies == 4
        assert state.entropy == pytest.approx(math.log(4))

    def test_from_strategy_counts_empty(self):
        state = EntropyCalculator.from_strategy_counts({})
        assert state.entropy == 0.0
        assert state.n_strategies == 0
