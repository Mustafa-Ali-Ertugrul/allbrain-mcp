from __future__ import annotations

from collections import Counter
from typing import Any

from allbrain.models.schemas import EventRead


class ReliabilityMetrics:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        counts = Counter(event.type for event in events)
        active_workers = {
            event.payload.get("worker_id")
            for event in events
            if event.type in {"worker_started", "worker_heartbeat"} and event.payload.get("worker_id")
        }
        stopped_workers = {
            event.payload.get("worker_id")
            for event in events
            if event.type in {"worker_stopped", "worker_stale"} and event.payload.get("worker_id")
        }
        active_leases = (
            counts["lease_acquired"] + counts["lease_renewed"] - counts["lease_released"] - counts["lease_expired"]
        )
        recoveries = counts["recovery_completed"] + counts["recovery_failed"]
        snapshots = counts["snapshot_restored"] + counts["snapshot_created"]
        return {
            "worker_uptime_ms": _worker_uptime(events),
            "active_workers": len(active_workers - stopped_workers),
            "stale_workers": counts["worker_stale"],
            "active_leases": max(active_leases, 0),
            "expired_leases": counts["lease_expired"],
            "lease_recovery_count": counts["task_requeued"],
            "duplicate_detection_count": counts["duplicate_detected"],
            "retry_count": counts["retry_scheduled"] + counts["task_requeued"] + counts["retry_attempted"],
            "recovery_success_rate": round(counts["recovery_completed"] / recoveries, 6) if recoveries else 0.0,
            "snapshot_hit_rate": round(counts["snapshot_restored"] / snapshots, 6) if snapshots else 0.0,
            "queue_depth_by_backend": _queue_depth(events),
            "worker_crash_count": counts["worker_stale"] + counts["recovery_started"],
            "circuit_breakers": _circuit_breakers(events),
            "cluster_health": {
                "registered_workers": counts["worker_registered"],
                "registered_nodes": counts["cluster_node_registered"],
                "queue_backend_outages": counts["queue_backend_outage"],
            },
        }


def _worker_uptime(events: list[EventRead]) -> int:
    starts: dict[str, Any] = {}
    total = 0
    for event in events:
        worker_id = event.payload.get("worker_id")
        if not isinstance(worker_id, str):
            continue
        if event.type == "worker_started":
            starts[worker_id] = event.created_at
        elif event.type == "worker_stopped" and worker_id in starts:
            total += int((event.created_at - starts[worker_id]).total_seconds() * 1000)
    return total


def _queue_depth(events: list[EventRead]) -> dict[str, int]:
    depth: Counter[str] = Counter()
    for event in events:
        backend = str(event.payload.get("queue_backend") or "unknown")
        if event.type == "queue_item_enqueued":
            depth[backend] += 1
        elif event.type in {"queue_item_dequeued", "task_requeued"}:
            depth[backend] = max(depth[backend] - 1, 0)
    return dict(sorted(depth.items()))


def _circuit_breakers(events: list[EventRead]) -> dict[str, str]:
    states: dict[str, str] = {}
    for event in events:
        name = str(event.payload.get("name") or event.payload.get("provider") or "unknown")
        if event.type == "circuit_breaker_opened":
            states[name] = "open"
        elif event.type == "circuit_breaker_half_opened":
            states[name] = "half_open"
        elif event.type == "circuit_breaker_closed":
            states[name] = "closed"
    return dict(sorted(states.items()))
