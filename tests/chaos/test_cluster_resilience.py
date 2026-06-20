from __future__ import annotations

from datetime import datetime, timedelta, timezone

from allbrain.distributed import ClusterManager, NodeIdentity, WorkerRegistry
from allbrain.resilience import Bulkhead, CircuitBreaker, FallbackRouter, RetryPolicy


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def test_cluster_registers_discovers_and_marks_stale_workers() -> None:
    registry = WorkerRegistry()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    registry.register("w1", node_id="node-a", capabilities={"skills": ["coding"]})
    registry.heartbeat("w1", now=now)

    assert registry.discover(capability="coding")[0]["worker_id"] == "w1"
    stale = registry.mark_stale(stale_after_seconds=30, now=now + timedelta(seconds=31))
    assert stale[0].status == "stale"


def test_cluster_manager_reports_health() -> None:
    manager = ClusterManager(node=NodeIdentity.create(node_id="node-a"))
    manager.register_worker("w1", capabilities={"skills": ["review"]})
    health = manager.health()
    assert health["active_workers"] == 1
    assert health["node"]["node_id"] == "node-a"


def test_circuit_breaker_state_machine_is_deterministic() -> None:
    clock = Clock()
    breaker = CircuitBreaker("openai", failure_threshold=2, recovery_seconds=10, clock=clock)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == "open"
    assert breaker.allow_request() is False
    clock.advance(10)
    assert breaker.allow_request() is True
    assert breaker.state == "half_open"
    breaker.record_success()
    assert breaker.state == "closed"


def test_retry_policy_fallback_router_and_bulkhead() -> None:
    assert RetryPolicy(max_attempts=2).decide(attempt=2).should_retry is False
    router = FallbackRouter({"openai": ["anthropic", "local"]})
    assert router.route("openai", failed={"openai"}) == "anthropic"
    bulkhead = Bulkhead({"provider:openai": 1})
    assert bulkhead.acquire("provider:openai") is True
    assert bulkhead.acquire("provider:openai") is False
    bulkhead.release("provider:openai")
    assert bulkhead.acquire("provider:openai") is True
