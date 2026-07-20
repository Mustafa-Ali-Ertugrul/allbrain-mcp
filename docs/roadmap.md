# AllBrain MCP v0.2.4 / v0.3.0 Roadmap

This roadmap outlines the targets for the upcoming versions, distinguishing between new features and technical debt reduction.

## v0.2.5 Backlog

* **Snapshot Generation Optimization:** ✅ DONE
  * `SnapshotEngine.build_snapshot()` now accepts `Iterable[EventRecord]` (internally materializes once via `list(events)` for the builder and cursor lookup).
  * `_snapshot.py` uses lazy `iter_events_through_cursor()` generator instead of list materialization.
* **Shared Facade Cleanup:** ✅ DONE
  * Deprecated re-exports in `_shared.py` facade now emit `DeprecationWarning` (via `__getattr__` lazy loader) prompting direct imports from `_events`, `_snapshot`, and `_tasks`. Internal modules migrated to direct imports. These re-exports will be removed in v0.3.0.
* **MCP Resource Subscriptions:**
  * Implement MCP resource subscription handling once FastMCP upstream adds native subscription support. (Deferred — FastMCP does not yet fully support it.)

## 1. Technical Debt Reduction

* **PipelineServices Refactoring:**
  * Make `PipelineServices` a strictly frozen dataclass as documented in `ARCHITECTURE.md`.
  * Replace instances of service mutation in `SystemDecisionPipeline.__init__` with `dataclasses.replace`.
* **Centralized Rate Limiting:**
  * Replace the current process-local `SlidingWindowCounter` with a SQLite/DB-coordinated rate limiter to correctly enforce limits across multiple parallel MCP clients.
* **Unpredictable Snapshot Leases:**
  * Enhance `_snapshot_lease` to use unique temp files with randomized suffixes, preventing local DoS attacks in multi-user environments.

## 2. New Features

* **Distributed Task Queue (v0.3.0):**
  * Stabilize experimental Redis and RabbitMQ queue adapters for sustained-load multi-worker consensus.
* **Semantic Query Improvements:**
  * Integrate hybrid search caching for vector embedding fetches in vector databases.
* **Incremental Snapshot Rollbacks:**
  * Support snapshot-level rollback without replaying full history from the initial event.
