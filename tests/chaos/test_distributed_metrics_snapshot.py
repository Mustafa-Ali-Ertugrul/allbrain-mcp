from __future__ import annotations

from allbrain.events import EventType
from allbrain.reliability import ReliabilityMetrics
from allbrain.server.app import get_reliability_status_impl, save_event_impl
from allbrain.snapshot import ClusterSnapshotBuilder
from tests.test_sprint12_memory_policy_ui import events, make_context


def test_distributed_metrics_include_cluster_and_circuit_state(tmp_path) -> None:
    context = make_context(tmp_path)
    assert save_event_impl(context, type=EventType.CLUSTER_NODE_REGISTERED.value, payload={"node_id": "node-a"}).ok
    assert save_event_impl(context, type=EventType.WORKER_REGISTERED.value, payload={"worker_id": "w1", "node_id": "node-a"}).ok
    assert save_event_impl(context, type=EventType.CIRCUIT_BREAKER_OPENED.value, payload={"name": "openai"}).ok
    assert save_event_impl(context, type=EventType.RETRY_ATTEMPTED.value, payload={"provider": "openai"}).ok

    metrics = ReliabilityMetrics().build(events(context))
    status = get_reliability_status_impl(context)

    assert metrics["cluster_health"]["registered_workers"] == 1
    assert metrics["circuit_breakers"]["openai"] == "open"
    assert metrics["retry_count"] == 1
    assert status.ok and status.data["cluster_health"]["registered_nodes"] == 1


def test_cluster_snapshot_captures_worker_registry_state(tmp_path) -> None:
    context = make_context(tmp_path)
    assert save_event_impl(
        context,
        type=EventType.WORKER_REGISTERED.value,
        payload={"worker_id": "w1", "node_id": "node-a", "capabilities": {"skills": ["coding"]}},
    ).ok

    snapshot = ClusterSnapshotBuilder().build(events(context))

    assert snapshot["kind"] == "cluster_snapshot"
    assert snapshot["workers"][0]["worker_id"] == "w1"
