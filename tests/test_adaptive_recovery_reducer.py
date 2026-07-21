from __future__ import annotations

import pytest

from allbrain.domains.governance.adaptive_recovery import (
    CHAIN_OUTCOME_ESCALATED,
    CHAIN_OUTCOME_FAILED,
    CHAIN_OUTCOME_SUCCESS,
    AdaptiveRecoveryReducer,
)
from allbrain.domains.governance.adaptive_recovery.events import (
    make_adaptive_recovery_completed_payload,
    make_chain_created_payload,
    make_step_failed_payload,
    make_step_started_payload,
    make_step_succeeded_payload,
    make_strategy_switched_payload,
)
from allbrain.events.schemas import EventType


def _event(etype: str, payload: dict, eid: str = "e1") -> object:
    return type(
        "FakeEvent",
        (),
        {
            "id": eid,
            "type": etype,
            "payload": payload,
        },
    )()


class TestAdaptiveRecoveryReducer:
    def test_apply_unknown_event_does_nothing(self):
        reducer = AdaptiveRecoveryReducer()
        reducer.apply(_event("unknown_type", {}))
        snap = reducer.snapshot()
        assert snap["total_created"] == 0
        assert snap["total_completed"] == 0

    def test_apply_chain_created_adds_active_chain(self):
        reducer = AdaptiveRecoveryReducer()
        payload = make_chain_created_payload(
            chain_id="cid1",
            fault_id="f1",
            fault_type="timeout",
            steps_count=2,
            strategies=["retry", "rollback"],
        )
        reducer.apply(_event(EventType.RECOVERY_CHAIN_CREATED.value, payload, eid="e1"))
        snap = reducer.snapshot()
        assert snap["total_created"] == 1
        assert len(snap["active_chains"]) == 1

    def test_apply_step_started_updates_current_index(self):
        reducer = AdaptiveRecoveryReducer()
        reducer.apply(
            _event(
                EventType.RECOVERY_CHAIN_CREATED.value,
                make_chain_created_payload(
                    chain_id="cid1",
                    fault_id="f1",
                    fault_type="timeout",
                    steps_count=2,
                    strategies=["retry", "rollback"],
                ),
                eid="e1",
            )
        )
        reducer.apply(
            _event(
                EventType.RECOVERY_STEP_STARTED.value,
                make_step_started_payload(chain_id="cid1", fault_id="f1", strategy="retry", order=1, step_index=0),
                eid="e2",
            )
        )
        snap = reducer.snapshot()
        active = snap["active_chains"][0]
        assert active.current_index == 0

    def test_apply_completed_success_moves_to_completed(self):
        reducer = AdaptiveRecoveryReducer()
        reducer.apply(
            _event(
                EventType.RECOVERY_CHAIN_CREATED.value,
                make_chain_created_payload(
                    chain_id="cid1", fault_id="f1", fault_type="timeout", steps_count=1, strategies=["retry"]
                ),
                eid="e1",
            )
        )
        reducer.apply(
            _event(
                EventType.ADAPTIVE_RECOVERY_COMPLETED.value,
                make_adaptive_recovery_completed_payload(
                    chain_id="cid1", fault_id="f1", outcome=CHAIN_OUTCOME_SUCCESS, steps_taken=1
                ),
                eid="e2",
            )
        )
        snap = reducer.snapshot()
        assert len(snap["completed_chains"]) == 1
        assert len(snap["active_chains"]) == 0
        assert snap["total_completed"] == 1

    def test_apply_completed_failed_moves_to_failed(self):
        reducer = AdaptiveRecoveryReducer()
        reducer.apply(
            _event(
                EventType.RECOVERY_CHAIN_CREATED.value,
                make_chain_created_payload(
                    chain_id="cid1", fault_id="f1", fault_type="timeout", steps_count=1, strategies=["retry"]
                ),
                eid="e1",
            )
        )
        reducer.apply(
            _event(
                EventType.ADAPTIVE_RECOVERY_COMPLETED.value,
                make_adaptive_recovery_completed_payload(
                    chain_id="cid1", fault_id="f1", outcome=CHAIN_OUTCOME_FAILED, steps_taken=0
                ),
                eid="e2",
            )
        )
        snap = reducer.snapshot()
        assert len(snap["failed_chains"]) == 1
        assert snap["total_failed"] == 1

    def test_apply_completed_escalated_moves_to_escalated(self):
        reducer = AdaptiveRecoveryReducer()
        reducer.apply(
            _event(
                EventType.RECOVERY_CHAIN_CREATED.value,
                make_chain_created_payload(
                    chain_id="cid1", fault_id="f1", fault_type="timeout", steps_count=1, strategies=["retry"]
                ),
                eid="e1",
            )
        )
        reducer.apply(
            _event(
                EventType.ADAPTIVE_RECOVERY_COMPLETED.value,
                make_adaptive_recovery_completed_payload(
                    chain_id="cid1", fault_id="f1", outcome=CHAIN_OUTCOME_ESCALATED, steps_taken=1
                ),
                eid="e2",
            )
        )
        snap = reducer.snapshot()
        assert len(snap["escalated_chains"]) == 1
        assert snap["total_escalated"] == 1

    def test_duplicate_event_id_skipped(self):
        reducer = AdaptiveRecoveryReducer()
        payload = make_chain_created_payload(
            chain_id="cid1", fault_id="f1", fault_type="timeout", steps_count=1, strategies=["retry"]
        )
        reducer.apply(_event(EventType.RECOVERY_CHAIN_CREATED.value, payload, eid="e1"))
        reducer.apply(_event(EventType.RECOVERY_CHAIN_CREATED.value, payload, eid="e1"))
        snap = reducer.snapshot()
        assert snap["total_created"] == 1

    def test_step_failed_and_succeeded_no_structural_change(self):
        reducer = AdaptiveRecoveryReducer()
        reducer.apply(
            _event(
                EventType.RECOVERY_CHAIN_CREATED.value,
                make_chain_created_payload(
                    chain_id="cid1",
                    fault_id="f1",
                    fault_type="timeout",
                    steps_count=2,
                    strategies=["retry", "rollback"],
                ),
                eid="e1",
            )
        )
        reducer.apply(
            _event(
                EventType.RECOVERY_STEP_FAILED.value,
                make_step_failed_payload(chain_id="cid1", fault_id="f1", strategy="retry", order=1),
                eid="e2",
            )
        )
        reducer.apply(
            _event(
                EventType.RECOVERY_STEP_SUCCEEDED.value,
                make_step_succeeded_payload(chain_id="cid1", fault_id="f1", strategy="rollback", order=2),
                eid="e3",
            )
        )
        snap = reducer.snapshot()
        assert len(snap["active_chains"]) == 1  # chain still active

    def test_strategy_switched_no_structural_change(self):
        reducer = AdaptiveRecoveryReducer()
        reducer.apply(
            _event(
                EventType.RECOVERY_CHAIN_CREATED.value,
                make_chain_created_payload(
                    chain_id="cid1",
                    fault_id="f1",
                    fault_type="timeout",
                    steps_count=2,
                    strategies=["retry", "rollback"],
                ),
                eid="e1",
            )
        )
        reducer.apply(
            _event(
                EventType.RECOVERY_STRATEGY_SWITCHED.value,
                make_strategy_switched_payload(
                    chain_id="cid1", fault_id="f1", from_strategy="retry", to_strategy="rollback"
                ),
                eid="e2",
            )
        )
        snap = reducer.snapshot()
        assert len(snap["active_chains"]) == 1

    def test_snapshot_structure(self):
        reducer = AdaptiveRecoveryReducer()
        snap = reducer.snapshot()
        assert "active_chains" in snap
        assert "completed_chains" in snap
        assert "failed_chains" in snap
        assert "escalated_chains" in snap
        assert "total_created" in snap
        assert "total_completed" in snap
        assert "total_failed" in snap
        assert "total_escalated" in snap
        assert "version" in snap

    def test_all_snapshots_structure(self):
        reducer = AdaptiveRecoveryReducer()
        result = reducer.all_snapshots()
        assert "default" in result
        assert isinstance(result["default"], dict)
