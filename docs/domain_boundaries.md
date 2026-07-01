# Domain ownership and dependency boundaries

AllBrain keeps its existing import paths for compatibility. Similar-sounding
packages are separate stages rather than duplicate implementations:

- **Recovery:** `resilience` detects and executes runtime recovery,
  `recovery_consensus` selects a strategy, `adaptive_recovery` sequences
  strategies, `self_repair` owns rollback/snapshots, and `soft_repair` blends
  policy versions.
- **Epistemic reasoning:** `belief` owns probabilistic state, `contradiction`
  detects conflicts, `evidence` scores support, `revision` applies revision
  policy, and `calibration` measures confidence accuracy.
- **Routing:** `routing` selects agents; `policy_routing` selects policy
  families. Neither package owns queue delivery.
- **Drift:** `drift` handles belief drift, `dynamics` handles capability trends,
  and `learning_safety` guards learning updates.

Domain packages must not import `server` or `storage`. Runtime orchestration
depends on `RuntimeContext` and `EventStore` protocols. Server and storage are
adapters at the system boundary; CI enforces these rules.

Redis and RabbitMQ adapters are experimental. Their real-service contracts
cover connectivity, persistence across reconnect, round-trip delivery, and
acknowledgement. They are not production-ready until atomic multi-worker lease,
crash recovery, redelivery, and sustained-load tests pass. SQLite remains the
default backend and PostgreSQL remains a CI compatibility target.
