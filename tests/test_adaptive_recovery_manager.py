from __future__ import annotations

import pytest

from allbrain.adaptive_recovery import (
    CHAIN_OUTCOME_ESCALATED,
    CHAIN_OUTCOME_FAILED,
    CHAIN_OUTCOME_SUCCESS,
    AdaptiveRecoveryManager,
)
from allbrain.events.schemas import EventType
from allbrain.recovery_consensus.model import CandidateStrategy


def _c(strategy: str = "retry", confidence: float = 0.8) -> CandidateStrategy:
    return CandidateStrategy(
        strategy=strategy,
        confidence=confidence,
        risk=0.2,
        estimated_success=0.7,
        explanation="test",
        fault_id="f1",
        component="test",
    )


class TestAdaptiveRecoveryManager:
    def test_run_chain_simple_success(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry")],
            attempt_outcomes=[True],
        )
        assert result["outcome"] == CHAIN_OUTCOME_SUCCESS
        assert result["steps_taken"] == 1
        assert result["fault_id"] == "f1"
        assert result["fault_type"] == "timeout"

    def test_run_chain_success_emits_events(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry")],
            attempt_outcomes=[True],
        )
        events = result["events"]
        types = [e["event_type"] for e in events]
        assert types == [
            EventType.RECOVERY_CHAIN_CREATED.value,
            EventType.RECOVERY_STEP_STARTED.value,
            EventType.RECOVERY_STEP_SUCCEEDED.value,
            EventType.ADAPTIVE_RECOVERY_COMPLETED.value,
        ]

    def test_run_chain_failure_switches_to_next_step(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry"), _c("rollback")],
            attempt_outcomes=[False, True],
        )
        assert result["outcome"] == CHAIN_OUTCOME_SUCCESS
        assert result["steps_taken"] == 2
        event_types = [e["event_type"] for e in result["events"]]
        assert EventType.RECOVERY_STRATEGY_SWITCHED.value in event_types
        assert EventType.RECOVERY_STEP_FAILED.value in event_types

    def test_run_chain_all_fail_escalates(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry"), _c("rollback")],
            attempt_outcomes=[False, False],
        )
        assert result["outcome"] == CHAIN_OUTCOME_ESCALATED
        assert result["steps_taken"] == 2
        event_types = [e["event_type"] for e in result["events"]]
        assert EventType.RECOVERY_STRATEGY_SWITCHED.value in event_types
        assert EventType.ADAPTIVE_RECOVERY_COMPLETED.value in event_types

    def test_run_chain_escalates_when_outcomes_exhaust_steps(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry")],
            attempt_outcomes=[False],
        )
        assert result["outcome"] == CHAIN_OUTCOME_ESCALATED
        assert result["steps_taken"] == 1

    def test_run_chain_empty_chain_fails(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[],
            attempt_outcomes=[True],
        )
        assert result["outcome"] == CHAIN_OUTCOME_FAILED
        assert result["steps_taken"] == 0
        assert result["steps"] == []

    def test_run_chain_empty_chain_emits_events(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[],
            attempt_outcomes=None,
        )
        event_types = [e["event_type"] for e in result["events"]]
        assert event_types == [EventType.RECOVERY_CHAIN_CREATED.value, EventType.ADAPTIVE_RECOVERY_COMPLETED.value]

    def test_run_chain_no_outcomes_returns_chain_without_simulation(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry"), _c("rollback")],
            attempt_outcomes=None,
        )
        assert result["outcome"] == ""
        assert result["steps_taken"] == 0
        assert len(result["steps"]) == 2
        event_types = [e["event_type"] for e in result["events"]]
        assert event_types == [EventType.RECOVERY_CHAIN_CREATED.value]

    def test_run_chain_does_not_exceed_chain_length(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry"), _c("rollback")],
            attempt_outcomes=[False, False, False],  # more outcomes than steps
        )
        assert result["steps_taken"] == 2

    def test_chain_id_deterministic(self):
        manager = AdaptiveRecoveryManager()
        r1 = manager.run_chain(fault_id="f1", fault_type="timeout", candidates=[_c("retry")], attempt_outcomes=[True])
        r2 = manager.run_chain(fault_id="f1", fault_type="timeout", candidates=[_c("retry")], attempt_outcomes=[True])
        assert r1["chain_id"] == r2["chain_id"]

    def test_chain_id_different_for_different_faults(self):
        manager = AdaptiveRecoveryManager()
        r1 = manager.run_chain(fault_id="f1", fault_type="timeout", candidates=[_c("retry")], attempt_outcomes=[True])
        r2 = manager.run_chain(
            fault_id="f2", fault_type="corruption", candidates=[_c("retry")], attempt_outcomes=[True]
        )
        assert r1["chain_id"] != r2["chain_id"]
