from __future__ import annotations

import pytest

from allbrain.domains.governance.adaptive_recovery import LinearSwitchPolicy, RecoveryChain, RecoveryStep


def _chain(steps: int = 3) -> RecoveryChain:
    return RecoveryChain(
        chain_id="cid1",
        fault_id="f1",
        fault_type="timeout",
        steps=tuple(
            RecoveryStep(
                strategy=f"s{i}",
                order=i + 1,
                confidence=0.8,
                fault_id="f1",
                chain_id="cid1",
            )
            for i in range(steps)
        ),
        current_index=0,
    )


class TestLinearSwitchPolicy:
    def test_next_step_returns_incremented_index(self):
        policy = LinearSwitchPolicy()
        chain = _chain(steps=3)
        result = policy.next_step(chain, 0)
        assert result == 1

    def test_next_step_second_step(self):
        policy = LinearSwitchPolicy()
        chain = _chain(steps=3)
        result = policy.next_step(chain, 1)
        assert result == 2

    def test_next_step_last_step_returns_none(self):
        policy = LinearSwitchPolicy()
        chain = _chain(steps=3)
        result = policy.next_step(chain, 2)
        assert result is None

    def test_next_step_single_step_chain_at_zero_returns_none(self):
        policy = LinearSwitchPolicy()
        chain = _chain(steps=1)
        result = policy.next_step(chain, 0)
        assert result is None

    def test_next_step_empty_chain_at_zero_returns_none(self):
        policy = LinearSwitchPolicy()
        chain = RecoveryChain(
            chain_id="cid1",
            fault_id="f1",
            fault_type="timeout",
            steps=(),
            current_index=0,
        )
        result = policy.next_step(chain, 0)
        assert result is None

    def test_next_step_negative_index_still_increments(self):
        policy = LinearSwitchPolicy()
        chain = _chain(steps=3)
        result = policy.next_step(chain, -1)
        assert result == 0

    def test_next_step_past_last_index_returns_none(self):
        policy = LinearSwitchPolicy()
        chain = _chain(steps=3)
        result = policy.next_step(chain, 10)
        assert result is None
