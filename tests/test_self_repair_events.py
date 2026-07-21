"""Unit tests for self_repair.events payload builders/validators.

Covers all make_* / validate_* functions plus the _check_* helpers.
"""

from __future__ import annotations

import pytest
from allbrain.self_repair.events import (
    make_policy_snapshotted_payload,
    make_rollback_completed_payload,
    make_rollback_triggered_payload,
    make_system_recovered_payload,
    make_validation_failed_payload,
    validate_policy_snapshotted,
    validate_policy_validation_failed,
    validate_rollback_completed,
    validate_rollback_triggered,
    validate_system_recovered,
)


class TestPolicySnapshotted:
    def test_valid_payload(self):
        p = make_policy_snapshotted_payload(snapshot_id="s1", fault_type="drift", policy_version=2, stability_score=0.8)
        assert p["snapshot_id"] == "s1"
        assert p["policy_version"] == 2
        assert p["stability_score"] == 0.8

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_policy_snapshotted({"snapshot_id": "s1", "fault_type": "drift"})

    def test_snapshot_id_must_be_str(self):
        with pytest.raises(ValueError, match="snapshot_id must be str"):
            validate_policy_snapshotted(
                {"snapshot_id": 5, "fault_type": "drift", "policy_version": 1, "stability_score": 0.5}
            )

    def test_policy_version_must_be_int_ge_one(self):
        with pytest.raises(ValueError, match="policy_version"):
            validate_policy_snapshotted(
                {"snapshot_id": "s1", "fault_type": "drift", "policy_version": 0, "stability_score": 0.5}
            )

    def test_stability_out_of_range(self):
        with pytest.raises(ValueError, match="stability_score must be in"):
            validate_policy_snapshotted(
                {"snapshot_id": "s1", "fault_type": "drift", "policy_version": 1, "stability_score": 1.5}
            )


class TestValidationFailed:
    def test_valid_payload(self):
        p = make_validation_failed_payload(
            fault_type="drift",
            policy_version=2,
            stability_score=0.3,
            failure_reasons=["cap dropped", "trend reversed"],
        )
        assert p["failure_reasons"] == ["cap dropped", "trend reversed"]

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_policy_validation_failed({"fault_type": "drift", "policy_version": 1})

    def test_failure_reasons_must_be_list(self):
        with pytest.raises(ValueError, match="failure_reasons must be list/tuple"):
            validate_policy_validation_failed(
                {
                    "fault_type": "drift",
                    "policy_version": 1,
                    "stability_score": 0.3,
                    "failure_reasons": "nope",
                }
            )


class TestRollbackTriggered:
    def test_valid_payload(self):
        p = make_rollback_triggered_payload(
            rollback_id="r1",
            fault_type="drift",
            from_version=3,
            to_version=2,
            strategy="revert",
            triggered_by="monitor",
        )
        assert p["strategy"] == "revert"

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_rollback_triggered({"rollback_id": "r1", "fault_type": "drift"})

    def test_from_version_must_be_int_ge_one(self):
        with pytest.raises(ValueError, match="from_version"):
            validate_rollback_triggered(
                {
                    "rollback_id": "r1",
                    "fault_type": "drift",
                    "from_version": 0,
                    "to_version": 1,
                    "strategy": "revert",
                    "triggered_by": "monitor",
                }
            )

    def test_strategy_must_be_str(self):
        with pytest.raises(ValueError, match="strategy must be str"):
            validate_rollback_triggered(
                {
                    "rollback_id": "r1",
                    "fault_type": "drift",
                    "from_version": 2,
                    "to_version": 1,
                    "strategy": 9,
                    "triggered_by": "monitor",
                }
            )


class TestRollbackCompleted:
    def test_valid_payload_success(self):
        p = make_rollback_completed_payload(
            rollback_id="r1", fault_type="drift", from_version=3, to_version=2, success=True
        )
        assert p["success"] is True

    def test_valid_payload_failure(self):
        p = make_rollback_completed_payload(
            rollback_id="r1", fault_type="drift", from_version=3, to_version=2, success=False
        )
        assert p["success"] is False

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_rollback_completed({"rollback_id": "r1", "fault_type": "drift"})

    def test_success_must_be_bool(self):
        with pytest.raises(ValueError, match="success must be bool"):
            validate_rollback_completed(
                {
                    "rollback_id": "r1",
                    "fault_type": "drift",
                    "from_version": 2,
                    "to_version": 1,
                    "success": "yes",
                }
            )


class TestSystemRecovered:
    def test_valid_payload_stable(self):
        p = make_system_recovered_payload(
            recovery_id="rec1",
            rollback_id="r1",
            fault_type="drift",
            stabilized=True,
            post_recovery_stability=0.9,
            cycles_to_stable=3,
        )
        assert p["stabilized"] is True
        assert p["cycles_to_stable"] == 3

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing"):
            validate_system_recovered({"recovery_id": "rec1", "rollback_id": "r1"})

    def test_stabilized_must_be_bool(self):
        with pytest.raises(ValueError, match="stabilized must be bool"):
            validate_system_recovered(
                {
                    "recovery_id": "rec1",
                    "rollback_id": "r1",
                    "fault_type": "drift",
                    "stabilized": 1,
                    "post_recovery_stability": 0.9,
                    "cycles_to_stable": 3,
                }
            )

    def test_post_recovery_stability_out_of_range(self):
        with pytest.raises(ValueError, match="post_recovery_stability must be in"):
            validate_system_recovered(
                {
                    "recovery_id": "rec1",
                    "rollback_id": "r1",
                    "fault_type": "drift",
                    "stabilized": True,
                    "post_recovery_stability": -0.1,
                    "cycles_to_stable": 3,
                }
            )

    def test_cycles_to_stable_must_be_int_ge_zero(self):
        with pytest.raises(ValueError, match="cycles_to_stable"):
            validate_system_recovered(
                {
                    "recovery_id": "rec1",
                    "rollback_id": "r1",
                    "fault_type": "drift",
                    "stabilized": True,
                    "post_recovery_stability": 0.9,
                    "cycles_to_stable": -1,
                }
            )
