from __future__ import annotations

import pytest

from allbrain.domains.governance.adaptive_recovery import (
    DEFAULT_MAX_CHAIN_LENGTH,
    PATTERN_MOVE_MIN_SAMPLES,
    PATTERN_MOVE_THRESHOLD,
    RecoveryChain,
    RecoveryStep,
    StrategyChain,
)
from allbrain.domains.governance.recovery_consensus.model import CandidateStrategy


def _candidate(
    strategy: str = "retry",
    confidence: float = 0.8,
    risk: float = 0.2,
    estimated_success: float = 0.7,
) -> CandidateStrategy:
    return CandidateStrategy(
        strategy=strategy,
        confidence=confidence,
        risk=risk,
        estimated_success=estimated_success,
        explanation="test",
        fault_id="f1",
        component="test",
    )


class TestStrategyChainBuild:
    def test_empty_candidates_returns_empty_chain(self):
        chain = StrategyChain().build([], fault_id="f1", fault_type="timeout")
        assert isinstance(chain, RecoveryChain)
        assert len(chain.steps) == 0
        assert chain.fault_id == "f1"
        assert chain.fault_type == "timeout"
        assert chain.current_index == 0

    def test_single_candidate_produces_one_step(self):
        chain = StrategyChain().build([_candidate(strategy="retry")], fault_id="f1", fault_type="timeout")
        assert len(chain.steps) == 1
        assert chain.steps[0].strategy == "retry"
        assert chain.steps[0].order == 1
        assert chain.steps[0].fault_id == "f1"

    def test_sorts_by_confidence_descending(self):
        c1 = _candidate(strategy="repair", confidence=0.9)
        c2 = _candidate(strategy="retry", confidence=0.7)
        c3 = _candidate(strategy="rollback", confidence=0.8)
        chain = StrategyChain().build([c1, c2, c3], fault_id="f1", fault_type="timeout")
        strategies = [s.strategy for s in chain.steps]
        assert strategies == ["repair", "rollback", "retry"]

    def test_ties_broken_by_estimated_success_ascending(self):
        c1 = _candidate(strategy="retry", confidence=0.8, estimated_success=0.6)
        c2 = _candidate(strategy="rollback", confidence=0.8, estimated_success=0.9)
        chain = StrategyChain().build([c1, c2], fault_id="f1", fault_type="timeout")
        strategies = [s.strategy for s in chain.steps]
        # Tiebreak: estimated_success ascending (retry 0.6 < rollback 0.9)
        assert strategies == ["retry", "rollback"]

    def test_max_chain_length_clamp(self):
        cands = [_candidate(strategy=f"s{i}", confidence=0.9 - i * 0.1) for i in range(10)]
        chain = StrategyChain(max_chain_length=3).build(cands, fault_id="f1", fault_type="timeout")
        assert len(chain.steps) == 3

    def test_default_max_chain_length_applied(self):
        cands = [_candidate(strategy=f"s{i}", confidence=0.9 - i * 0.1) for i in range(10)]
        chain = StrategyChain().build(cands, fault_id="f1", fault_type="timeout")
        assert len(chain.steps) == DEFAULT_MAX_CHAIN_LENGTH

    def test_chain_id_deterministic(self):
        chain1 = StrategyChain().build([_candidate("retry")], fault_id="f1", fault_type="timeout")
        chain2 = StrategyChain().build([_candidate("retry")], fault_id="f1", fault_type="timeout")
        assert chain1.chain_id == chain2.chain_id

    def test_chain_id_different_for_different_fault_ids(self):
        chain1 = StrategyChain().build([_candidate("retry")], fault_id="f1", fault_type="timeout")
        chain2 = StrategyChain().build([_candidate("retry")], fault_id="f2", fault_type="timeout")
        assert chain1.chain_id != chain2.chain_id

    def test_chain_id_different_for_different_fault_types(self):
        chain1 = StrategyChain().build([_candidate("retry")], fault_id="f1", fault_type="timeout")
        chain2 = StrategyChain().build([_candidate("retry")], fault_id="f1", fault_type="corruption")
        assert chain1.chain_id != chain2.chain_id

    def test_chain_id_length_is_16_chars(self):
        chain = StrategyChain().build([_candidate("retry")], fault_id="f1", fault_type="timeout")
        assert len(chain.chain_id) == 16

    def test_step_confidence_clamped_to_zero_one(self):
        c = _candidate(strategy="retry", confidence=1.5)
        chain = StrategyChain().build([c], fault_id="f1", fault_type="timeout")
        assert chain.steps[0].confidence == 1.0

    def test_step_confidence_low_bound(self):
        c = _candidate(strategy="retry", confidence=-0.5)
        chain = StrategyChain().build([c], fault_id="f1", fault_type="timeout")
        assert chain.steps[0].confidence == 0.0


class TestMemoryBias:
    def test_memory_none_does_not_reorder(self):
        chain = StrategyChain().build(
            [
                _candidate(strategy="retry", confidence=0.9),
                _candidate(strategy="rollback", confidence=0.8),
            ],
            fault_id="f1",
            fault_type="timeout",
        )
        assert [s.strategy for s in chain.steps] == ["retry", "rollback"]

    def test_memory_with_low_success_moves_to_end(self):
        class FakeMemory:
            def retrieve(self, fault_type: str) -> dict:
                return {
                    "patterns": [
                        {"strategy": "retry", "success_rate": 0.1, "attempts": 10},
                    ]
                }

        chain = StrategyChain().build(
            [
                _candidate(strategy="rollback", confidence=0.8),
                _candidate(strategy="retry", confidence=0.9),
            ],
            fault_id="f1",
            fault_type="timeout",
            memory=FakeMemory(),
        )
        strategies = [s.strategy for s in chain.steps]
        assert strategies == ["rollback", "retry"]

    def test_memory_below_min_samples_not_moved(self):
        class FakeMemory:
            def retrieve(self, fault_type: str) -> dict:
                return {
                    "patterns": [
                        {"strategy": "retry", "success_rate": 0.1, "attempts": 2},
                    ]
                }

        chain = StrategyChain().build(
            [
                _candidate(strategy="rollback", confidence=0.8),
                _candidate(strategy="retry", confidence=0.9),
            ],
            fault_id="f1",
            fault_type="timeout",
            memory=FakeMemory(),
        )
        # retry has low rate but not enough samples, stays in original order
        assert [s.strategy for s in chain.steps] == ["retry", "rollback"]

    def test_memory_above_threshold_not_moved(self):
        class FakeMemory:
            def retrieve(self, fault_type: str) -> dict:
                return {
                    "patterns": [
                        {"strategy": "retry", "success_rate": 0.8, "attempts": 10},
                    ]
                }

        chain = StrategyChain().build(
            [
                _candidate(strategy="rollback", confidence=0.8),
                _candidate(strategy="retry", confidence=0.9),
            ],
            fault_id="f1",
            fault_type="timeout",
            memory=FakeMemory(),
        )
        assert [s.strategy for s in chain.steps] == ["retry", "rollback"]

    def test_memory_exception_falls_back(self):
        class BrokenMemory:
            def retrieve(self, fault_type: str) -> dict:
                raise RuntimeError("boom")

        chain = StrategyChain().build(
            [_candidate(strategy="retry", confidence=0.9)],
            fault_id="f1",
            fault_type="timeout",
            memory=BrokenMemory(),
        )
        assert len(chain.steps) == 1
        assert chain.steps[0].strategy == "retry"

    def test_best_historical_rate_promoted_to_front(self):
        class FakeMemory:
            def retrieve(self, fault_type: str) -> dict:
                return {
                    "patterns": [
                        {"strategy": "rollback", "success_rate": 0.9, "attempts": 10},
                        {"strategy": "repair", "success_rate": 0.6, "attempts": 8},
                        {"strategy": "retry", "success_rate": 0.1, "attempts": 10},
                    ]
                }

        chain = StrategyChain().build(
            [
                _candidate(strategy="repair", confidence=0.9),
                _candidate(strategy="retry", confidence=0.8),
                _candidate(strategy="rollback", confidence=0.7),
            ],
            fault_id="f1",
            fault_type="timeout",
            memory=FakeMemory(),
        )
        # rollback has best historical rate, promoted to front
        # retry (low success) moved to end
        strategies = [s.strategy for s in chain.steps]
        assert strategies[0] == "rollback"
        assert strategies[-1] == "retry"
