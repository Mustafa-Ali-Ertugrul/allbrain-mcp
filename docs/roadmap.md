# AllBrain MCP v0.2.4 / v0.3.0 Roadmap

This roadmap outlines the targets for the upcoming versions, distinguishing between new features and technical debt reduction.

## v1.1.1 (2026-09-24) — Shipped

* **Zombie-Session Defense:** ✅ DONE
  * `touch_session` refuses heartbeats on terminal rows (no more `last_heartbeat_at > ended_at` drift).
  * `finalize_active_session` re-reads the authoritative DB row — no duplicate `session_summary` after cross-process stale reconciliation.
  * Heartbeat loop detaches sessions closed/reconciled elsewhere; `close_session` tool aligns process context immediately.
* **Dependency Security Sweep:** ✅ DONE
  * GitPython 3.1.50 → 3.1.62 (closes 15 advisories incl. CVSS 9.3 conditional RCE).
  * cryptography 49.0.0 → 50.0.1 (closes CVE-2026-69247).
* **Dashboard Hardening:** ✅ DONE
  * Bearer-token auth on all `/api/*` endpoints (per-start random token; `ALLBRAIN_DASHBOARD_TOKEN` override).
  * CORS `*` removed; explicit `ALLBRAIN_DASHBOARD_ALLOWED_ORIGINS` allowlist.
  * `limit` input validation (1–1000, 400 on bad input).
  * Repaired broken `/api/*` endpoints (`list_events` missing `project_path`).

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
