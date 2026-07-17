# Sprint 14 Distributed Execution & Resilience Architecture

Sprint 14 upgrades Sprint 13's reliability-ready execution model toward distributed execution. The implementation keeps distributed mode optional and preserves single-node defaults.

## Key Additions

- `allbrain.distributed`: node identity, worker registry, and cluster health reporting.
- `allbrain.resilience`: circuit breaker, retry policy, fallback router, and bulkhead isolation.
- Redis and RabbitMQ queue adapters are no longer stubs. They provide deterministic lease-aware queue semantics without requiring external services in tests, while keeping constructor surfaces ready for future real client integration.
- Reliability metrics now include cluster health, worker crash count, retry attempts, queue backend outages, and circuit breaker states.
- Cluster snapshots capture worker registry state and remain event-derived.

## State Machines

Circuit breaker:

```text
closed -> open -> half_open -> closed
closed -> open -> half_open -> open
```

Queue delivery:

```text
enqueued -> leased -> acked
enqueued -> leased -> nack/requeue -> leased -> acked
enqueued -> leased -> lease_expired -> recoverable -> leased
```

## Rollout

- Default runtime remains single-node and in-memory unless configured otherwise.
- SQLite remains the persistent local backend.
- Redis/RabbitMQ adapters are deterministic and distributed-semantics-compatible in v1; external broker integration can be added behind the same `TaskQueue` contract.
- Chaos tests validate duplicate delivery, lease recovery, nack/requeue, circuit breaker activation, bulkhead isolation, and cluster metric derivation.
