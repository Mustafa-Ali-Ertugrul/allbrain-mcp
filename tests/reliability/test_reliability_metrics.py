from __future__ import annotations

from allbrain.events import EventType
from allbrain.reliability import ReliabilityMetrics
from allbrain.server.app import get_reliability_status_impl, get_system_metrics_impl, save_event_impl
from tests.test_sprint12_memory_policy_ui import events, make_context


def test_reliability_metrics_are_event_derived(tmp_path) -> None:
    context = make_context(tmp_path)
    assert save_event_impl(context, type=EventType.WORKER_STARTED.value, payload={"worker_id": "w1"}).ok
    assert save_event_impl(context, type=EventType.DUPLICATE_DETECTED.value, payload={"idempotency_key": "k1"}).ok
    assert save_event_impl(context, type=EventType.LEASE_EXPIRED.value, payload={"lease_id": "l1"}).ok
    assert save_event_impl(context, type=EventType.TASK_REQUEUED.value, payload={"task_id": "t1", "queue_backend": "sqlite"}).ok
    assert save_event_impl(context, type=EventType.RECOVERY_COMPLETED.value, payload={"task_id": "t1"}).ok

    metrics = ReliabilityMetrics().build(events(context))

    assert metrics["duplicate_detection_count"] == 1
    assert metrics["expired_leases"] == 1
    assert metrics["lease_recovery_count"] == 1
    assert metrics["recovery_success_rate"] == 1.0


def test_reliability_status_mcp_impl_and_system_metrics_are_additive(tmp_path) -> None:
    context = make_context(tmp_path)
    assert save_event_impl(context, type=EventType.WORKER_HEARTBEAT.value, payload={"worker_id": "w1"}).ok

    status = get_reliability_status_impl(context)
    system = get_system_metrics_impl(context)

    assert status.ok
    assert status.data["active_workers"] == 1
    assert system.ok
    assert "reliability" in system.data
