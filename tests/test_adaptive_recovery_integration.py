from __future__ import annotations

import pytest

from allbrain.adaptive_recovery import (
    CHAIN_OUTCOME_ESCALATED,
    CHAIN_OUTCOME_FAILED,
    CHAIN_OUTCOME_SUCCESS,
    AdaptiveRecoveryManager,
    AdaptiveRecoveryReducer,
)
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


def _event(etype: str, payload: dict, eid: str = "e1") -> object:
    return type("FakeEvent", (), {
        "id": eid,
        "type": etype,
        "payload": payload,
    })()


class TestAdaptiveRecoveryIntegration:
    def test_manager_events_replayable_by_reducer(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry"), _c("rollback")],
            attempt_outcomes=[True],
        )

        reducer = AdaptiveRecoveryReducer()
        for i, ev in enumerate(result["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"ev{i}"))

        snap = reducer.snapshot()
        assert snap["total_created"] == 1
        assert snap["total_completed"] == 1
        assert len(snap["completed_chains"]) == 1
        chain = snap["completed_chains"][0]
        assert chain.chain_id == result["chain_id"]

    def test_manager_failure_chain_replayable(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry"), _c("rollback")],
            attempt_outcomes=[False, True],
        )

        reducer = AdaptiveRecoveryReducer()
        for i, ev in enumerate(result["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"ev{i}"))

        snap = reducer.snapshot()
        assert snap["total_completed"] == 1
        assert len(snap["completed_chains"]) == 1

    def test_manager_escalated_chain_replayable(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("retry")],
            attempt_outcomes=[False],
        )

        reducer = AdaptiveRecoveryReducer()
        for i, ev in enumerate(result["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"ev{i}"))

        snap = reducer.snapshot()
        assert snap["total_escalated"] == 1
        assert len(snap["escalated_chains"]) == 1

    def test_empty_chain_replayable(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[],
        )

        reducer = AdaptiveRecoveryReducer()
        for i, ev in enumerate(result["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"ev{i}"))

        snap = reducer.snapshot()
        assert snap["total_failed"] == 1
        assert len(snap["failed_chains"]) == 1

    def test_multiple_chains_replayed(self):
        manager = AdaptiveRecoveryManager()
        r1 = manager.run_chain(fault_id="f1", fault_type="timeout", candidates=[_c("retry")], attempt_outcomes=[True])
        r2 = manager.run_chain(fault_id="f2", fault_type="corruption", candidates=[_c("rollback")], attempt_outcomes=[False])
        r3 = manager.run_chain(fault_id="f3", fault_type="crash", candidates=[_c("repair"), _c("isolate")], attempt_outcomes=[False, False])

        reducer = AdaptiveRecoveryReducer()
        for i, ev in enumerate(r1["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"a{i}"))
        for i, ev in enumerate(r2["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"b{i}"))
        for i, ev in enumerate(r3["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"c{i}"))

        snap = reducer.snapshot()
        assert snap["total_created"] == 3
        assert snap["total_completed"] == 1
        # r2: single step fails, exhausted → escalated
        # r3: two steps fail, exhausted → escalated
        assert snap["total_escalated"] == 2
        assert snap["total_failed"] == 0

    def test_manager_with_memory_bias_integration(self):
        class FakeMemory:
            def retrieve(self, fault_type: str) -> dict:
                return {
                    "patterns": [
                        {"strategy": "retry", "success_rate": 0.1, "attempts": 10},
                    ]
                }

        manager = AdaptiveRecoveryManager(memory=FakeMemory())
        result = manager.run_chain(
            fault_id="f1",
            fault_type="timeout",
            candidates=[_c("rollback", confidence=0.7), _c("retry", confidence=0.9)],
            attempt_outcomes=[True],
        )
        # rollback should be first due to memory bias
        assert result["steps"][0]["strategy"] == "rollback"
        assert result["outcome"] == CHAIN_OUTCOME_SUCCESS

    def test_reducer_idempotent_with_duplicate_events(self):
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(fault_id="f1", fault_type="timeout", candidates=[_c("retry")], attempt_outcomes=[True])

        reducer = AdaptiveRecoveryReducer()
        for i, ev in enumerate(result["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"ev{i}"))
        snap1 = reducer.snapshot()

        # Re-apply same events
        for i, ev in enumerate(result["events"]):
            reducer.apply(_event(ev["event_type"], ev, eid=f"ev{i}"))
        snap2 = reducer.snapshot()

        assert snap1["total_created"] == snap2["total_created"]
        assert snap1["total_completed"] == snap2["total_completed"]

    def test_manager_default_chain_length(self):
        candidates = [_c(strategy=f"s{i}", confidence=0.9 - i * 0.1) for i in range(10)]
        manager = AdaptiveRecoveryManager()
        result = manager.run_chain(fault_id="f1", fault_type="timeout", candidates=candidates, attempt_outcomes=[True])
        assert len(result["steps"]) == 4  # DEFAULT_MAX_CHAIN_LENGTH

    def test_manager_custom_chain_length(self):
        candidates = [_c(strategy=f"s{i}", confidence=0.9 - i * 0.1) for i in range(10)]
        manager = AdaptiveRecoveryManager(max_chain_length=2)
        result = manager.run_chain(fault_id="f1", fault_type="timeout", candidates=candidates, attempt_outcomes=[True])
        assert len(result["steps"]) == 2
