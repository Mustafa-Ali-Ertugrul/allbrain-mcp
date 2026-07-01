# Database scaling policy

SQLite remains the default local backend. The nightly MCP stress test is the
operational capacity signal and must complete every write with zero lock or
unexpected errors. Its latency budgets are p95 <= 250 ms and p99 <= 1,500 ms.

A PostgreSQL production rollout review is triggered after three consecutive
nightly budget failures. A single failure is investigated as a regression but
does not change the default backend. PostgreSQL is the primary scale-out target;
a time-series store may receive derived telemetry but is not the authoritative
event log because replay, causal links, sessions, and queue leases are relational.
