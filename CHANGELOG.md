# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-07-21

### Added
- **Production GA Release (v1.0.0):** Production-ready release of AllBrain MCP event-sourced memory and multi-agent runtime.
- **Complete Bounded Context Architecture:** All 73 domain modules migrated into canonical namespace `allbrain.domains.*` across 6 Bounded Contexts:
  - `allbrain.domains.reasoning` (10 modules: `decision`, `counterfactual`, `scenarios`, `foresight`, `uncertainty`, `meta_reasoning`, `tradeoff_engine`, `information_seeking`, `intent`, `objective_system`)
  - `allbrain.domains.analysis` (17 modules: `world`, `belief`, `causal`, `contradiction`, `semantic`, `attention`, `attribution`, `compression`, `dynamics`, `episodic`, `evidence`, `failure_memory`, `fusion`, `graph`, `predictive_failure`, `context`, `drift`)
  - `allbrain.domains.learning` (12 modules: `learning`, `capabilities`, `meta_policy`, `calibration`, `evolution`, `coevolution`, `self_play`, `learning_graph`, `learning_safety`, `meta_optimizer`, `meta_scoring`, `meta_meta_scoring`)
  - `allbrain.domains.governance` (12 modules: `policy`, `governance`, `reliability`, `resilience`, `self_repair`, `soft_repair`, `adaptive_recovery`, `recovery_consensus`, `mitigation_learning`, `policy_competition`, `policy_routing`, `value_alignment`)
  - `allbrain.domains.memory` (12 modules: `memory`, `replay`, `resume`, `gitbrain`, `telemetry`, `observability`, `metrics`, `foundations`, `runtime_core`, `revision`, `ui`, `api`)
  - `allbrain.domains.collaboration` (10 modules: `collaboration`, `conflict`, `merge`, `arbitration`, `reputation`, `distributed`, `workflow`, `workspace`, `agents`, `routing`)
- **Performance Benchmark Suite (`scripts/benchmark_performance.py`):**
  - Cold startup time: **0.109s** (target $\le 5.0$s)
  - Event throughput: **451–604 eps** across small, medium, and large payloads (target $\ge 400$ eps)
  - Snapshot generation: **0.091s** for 10k events (target $\le 10.0$s)
  - Memory footprint: **~150 MB RSS** (target $\le 512$ MB)
  - Auto-generated benchmark report in `docs/performance_benchmarks.md`.
- **Comprehensive Functional Verification Suite (`scripts/verify_functional_requirements.py`):**
  - MCP Tool Completeness (51/51 registered tools verified against FastMCP JSON-RPC schemas)
  - 4-step E2E Decision Pipeline (Preparation → Reasoning → Feedback → Learning)
  - Multi-agent Conflict Resolution (`ConflictDetector` + `ConflictResolver`)
  - Event Sourcing & Snapshot Restore Integrity
  - Session Management & Worker Lease Lifecycle (`QueueCoordinator`)
  - Auto-generated functional report in `docs/functional_verification.md`.
- **Security Audit & Hardening Report (`docs/security_audit.md`):**
  - 0 High/Critical vulnerabilities across 48,521 LOC (Bandit SAST scan).
  - Multi-layer secret redaction (13+ high-entropy regexes, field denylists, ReDoS guards, Pydantic error masking).
  - Strict input validation via Pydantic `BaseInputModel` (`extra='forbid'`, strict mode, null-byte rejection, size caps).
  - Filesystem sandboxing via `canonicalize_project_path()` and `ALLBRAIN_ALLOWED_PROJECT_ROOTS`.
  - Process-local thread-safe dual-window rate limiting (`SlidingWindowCounter`).
- **Comprehensive v1.0 Documentation:**
  - `docs/ARCHITECTURE.md`: Updated 4-tier cognitive architecture and canonical bounded context reference.
  - `docs/upgrade.md`: Step-by-step v0.4.x → v1.0 migration guide.

### Changed
- Promoted package classifier to `Development Status :: 5 - Production/Stable`.
- Standardized environment variables:
  - `ALLBRAIN_ALLOWED_PROJECT_ROOTS` (replaces deprecated `ALLOWED_PROJECT_ROOTS`).
  - `ALLBRAIN_RATE_LIMIT_RPM` (default: 100,000 requests/min).
  - `ALLBRAIN_RATE_LIMIT_RPS` (default: 1,000 requests/sec).

### Deprecated
- Legacy root package imports (`allbrain.<module>`) emit `DeprecationWarning` via `_compat.shim_package`.
- **Legacy root shims will be completely removed in v2.0.0.** All callers should migrate to `allbrain.domains.<context>.<module>`.

## [0.4.1] - 2026-07-20

### Changed
- Migrated 17 analysis-domain packages to `allbrain.domains.analysis`:
  `attention`, `attribution`, `belief`, `causal`, `compression`, `context`,
  `contradiction`, `drift`, `dynamics`, `episodic`, `evidence`, `failure_memory`,
  `fusion`, `graph`, `predictive_failure`, `semantic`, `world`.
- Legacy analysis package imports remain available via `allbrain._compat.shim_package` shims.
- Submodule imports like `allbrain.world.manager` continue to resolve seamlessly via shims.

### Deprecated
- Legacy top-level analysis imports (e.g., `allbrain.world`, `allbrain.causal`) emit `DeprecationWarning`.
- Legacy analysis paths will be removed in `v2.0.0`.
- Use canonical imports from `allbrain.domains.analysis` instead.

### Fixed
- Fixed pre-existing ruff issues (UP037 and E501) in `src/allbrain/world/manager.py`.

## [0.4.0] - 2026-07-20

### Changed
- **BREAKING (0.x semver):** Migrated all 10 reasoning modules to `allbrain.domains.reasoning.*`:
  `counterfactual`, `scenarios`, `foresight`, `meta_reasoning`, `uncertainty`, `decision`, `information_seeking`, `intent`, `objective_system`, `tradeoff_engine`.
- **Backward-Compatible Shims:** Top-level `allbrain.<mod>` files re-export public APIs with `DeprecationWarning` (slated for removal in v2.0.0).
- **Internal Imports Migrated:** `server/tools/`, `snapshot/`, `contradiction/`, `predictive_failure/`, `replay/`, `runtime_core/`, `reducers/`, and `tests/` now import directly from `allbrain.domains.reasoning.*`.
- **Reasoning Context Facade:** `allbrain.domains.reasoning.__init__.py` re-exports all 10 modules and declares them in `__all__`.

### Added
- `WorldModel.from_events()` classmethod: rebuild WorldModel state from event history for pipeline warm-starting (API surface, pipeline integration ships in v0.4.1).
- `WorldModel.serialize_transitions()` method: serialize learned transition/prediction state for event-store persistence.
- `docs/ARCHITECTURE.md` **Design Philosophy** section: 5-layer cognitive architecture (Bayesian Epistemology → Metacognition → World Modeling → Decision → Memory).
- `docs/adr/` — 6 Architecture Decision Records (ADR-001 through ADR-006) documenting key migration, compatibility, and infrastructure decisions.
- `tests/test_domains_migration.py`: 4 regression tests verifying new-path imports, shim deprecation warnings, context facade re-exports, and Golden Rule isolation.

## [0.3.0] - 2026-07-19

### Added
- **Bounded Context Scaffold:** New `allbrain.domains.*` namespace with 6 contexts (`reasoning`, `governance`, `learning`, `collaboration`, `analysis`, `memory`) documenting the v0.4.0 module-consolidation target. No module moves yet — Phase 1 is scaffold + docs.
- **Architecture Doc:** `docs/architecture.md` with the full 73-module → 6-context mapping table, a Mermaid dependency diagram, and a coupling ranking for v0.4.0 cleanup candidates.

### Deprecated
- `allbrain.drift` and `allbrain.learning_graph` now emit `DeprecationWarning` at import time. Both are reducer-only (no server-tool, CLI, or public-API importers) and are slated for removal in v0.4.0.



### Changed
- **SnapshotEngine Iterable Acceptance:** `SnapshotEngine.build_snapshot()` now accepts `Iterable[EventRecord]` and materializes it once internally; `_snapshot.py` switched from `load_events_through_cursor()` (eager list) to the lazy `iter_events_through_cursor()` generator. Closes the v0.2.5 backlog TODO.
- **Deprecated Facade Re-exports:** Public re-exports in `_shared.py` now emit `DeprecationWarning` via a `__getattr__` lazy loader, prompting direct imports from `_events`, `_snapshot`, and `_tasks`. Internal tool modules migrated to direct imports. These re-exports will be removed in v0.3.0.
- **README Consistency:** Full-profile tool count corrected to 51 (was inconsistently 50/51), matching the authoritative registration count.

### Fixed
- **Test `test_git_fingerprint_computed_outside_lock`:** Replaced the `RLock._is_owned()` call (absent on some Python builds → `AttributeError`) with a lock-depth tracking wrapper that verifies `GitBrain.build_fingerprint()` runs outside the session mutex.



### Added
- 14 regression tests in `tests/test_v024_fixes.py` protecting performance, safety, and concurrency changes.

### Changed
- **StateEngine Single-Pass Loop:** Merged `final_machine` and `delta_machine` loops in `StateEngine.apply_events()` to eliminate redundant iteration ($O(2n) \to O(n)$).
- **QueueCoordinator claim() Locking:** Switched `claim()` from `open_session` to `open_write_session` to enforce SQLite `BEGIN IMMEDIATE` transaction locking and prevent concurrent double-assignments.
- **Redaction Value-Based Fallback:** Removed generic `"key"` and `"keys"` from `_SAFE_KEY_DENYLIST` to evaluate them dynamically. If the value matches a secret pattern, the value is masked; safe values remain untouched.
- **Lazy Event Streaming:** Added `iter_events_through_cursor()` generator for batched, memory-efficient event streaming without full list materialization.
- **Interruptible DB Backoff:** Replaced `time.sleep` with `threading.Event().wait()` in the database retry loop (then reverted to honest `time.sleep` with clear retry purpose following code review).
- **Subprocess Lock Scope Reduction:** Moved the blocking `GitBrain.build_fingerprint()` subprocess call out of the `_session_lock` mutex in `record_git_changes()`.
- **Shared Facade Decomposition:** Split the 460-line monolithic `_shared.py` file into four focused domain submodules: `_events.py` (cursor batching), `_snapshot.py` (lease management), `_tasks.py` (selection decisions & metrics), and `_shared.py` (facade with core tool utilities). Removed unused private re-exports.
- **SnapshotEngine Iterable Acceptance:** `SnapshotEngine.build_snapshot()` now accepts `Iterable[EventRecord]` and materializes it once internally; `_snapshot.py` switched from `load_events_through_cursor()` (eager list) to the lazy `iter_events_through_cursor()` generator. Closes the v0.2.5 backlog TODO.
- **Deprecated Facade Re-exports:** Public re-exports in `_shared.py` now emit `DeprecationWarning` via a `__getattr__` lazy loader, prompting direct imports from `_events`, `_snapshot`, and `_tasks`. Internal tool modules migrated to direct imports. These re-exports will be removed in v0.3.0.

## [0.2.3] - 2026-07-19

### Added

- `get_context_pack` compact agent context tool.
- Multi-agent claim loop: `create_task(enqueue=…)` and queue coordinator wiring.
- Ops: `allbrain doctor --clients` and `allbrain restart --all`.
- MCP contract polish: event type aliases, `ToolResult.error_code`, slim resume/orchestrate detail mode.
- **Env Variable Prefixing:** `ALLBRAIN_ALLOWED_PROJECT_ROOTS` eklendi, eski değişken için `DeprecationWarning` eklendi.

### Changed (Glama)

- Glama evaluation now uses the balanced 10-tool `core` profile instead of the 3-tool `minimal` profile.
- Added the required `maintainers` metadata so Glama recognizes `glama.json`.
- Glama's public tool surface is reduced from the full profile to a focused core set for reliable tool selection.
- README'ye "Glama MCP Portal" bölümü eklendi.
- `tests/test_mcp_tool_profiles.py`'a `test_minimal_tool_profile_is_exact_and_unique` regression testi eklendi.

### Fixed

- Production hardening: event stream unique invariant on ORM model; redaction key normalize (headers/query); independent snapshot check interval.
- **Security Hardening (M7 & M8):** OpenAI key redaction pattern tightened to `{40,}`, recursive payload redaction depth limit (`_MAX_SANITIZE_DEPTH = 32`) to prevent stack overflow.
- **Queue Coordinator Concurrency:** `QueueCoordinator.enqueue_task` rewritten to use `open_write_session` and catch `IntegrityError` to resolve concurrent idempotency races.
- **Session Lock Optimization:** `ensure_session_started` kilit süresi daraltıldı. Git fingerprinting ve veritabanı yazımları kilit dışına çıkarıldı.
- **Git Observer Cache:** `record_git_changes` için `context._recorded_git_keys` cache'i eklenerek her tool çağrısında oluşan O(n) disk okuma yükü kaldırıldı.
- **Telemetry Dict Outcome:** `_result_outcome` telemetry parsing'i dict sonuçları düzgün okuyacak şekilde güncellendi.
- Restart ops: process match no longer treats `restart` as `start`; installer resolves real package repo root.

## [0.2.1] - 2026-07-03

### Added

- `update_task` and `delete_task` tools for complete CRUD on task objects.
- `TASK_UPDATED` and `TASK_DELETED` event types with stable event-sourcing.
- TaskStateReducer now handles `TASK_UPDATED` (goal/kind/files) and `TASK_DELETED` (soft-delete + exclusions).
- Glama MCP server profile (`glama.json`) for improved discovery.

### Changed

- **Consolidated tools** for better Glama Server Coherence: Git 3→1 (`git_info`), Workflow 3→1 (`workflow_info`), UI 4→1 (`ui_view`). Total tools: 50.
- All 50+ tool docstrings enriched with TDQS-quality descriptions (goal, contract, errors, examples, edge cases, relations).
- `SemanticEventType` expanded to include `TASK_UPDATED` and `TASK_DELETED`.

### Fixed

- Pre-commit test constant fixture now uses `tqdm.write()` to avoid pytest stdout capturing deadlock.

## [0.2.0] - 2026-07-03

### Added

- MIT License added.
- Docstrings added to all 50+ MCP tool wrappers for better discoverability.
- Causal graph cycle detection via Tarjan SCC and weakest-edge pruning.
- `build_causal_graph(..., resolve_cycles=True)` for guaranteed DAG output.
- Counterfactual alternative pruning by risk, confidence, and cost thresholds.
- `CounterfactualEngine.analyze(...)` now accepts `risk_threshold`, `confidence_threshold`, `cost_threshold`.
- Constraint engine live-lock protection with consecutive-failure escalation (attention → supervisor).
- Alignment score oscillation detection in `AlignmentScoreTracker`.
- Self-modification repetitive rejection guard (`SelfModificationGuard`) with configurable window and threshold.

### Changed

- README updated to reflect 2077+ tests, 80%+ coverage, and new Layer 1 / Layer 3 capabilities.
- `pyproject.toml` now declares `license = "MIT"` and `license-files = ["LICENSE"]`.
- `AlternativeGenerator` now accepts an optional simulator and offers `generate_with_pruning()`.
- `CounterfactualEngine` now wires the simulator into the generator for pruning support.

### Fixed

- Causal graph self-loops are now detected and pruned correctly.
- `AlignmentResult` now carries `consecutive_failures`, `escalation_level`, and `oscillation_detected`.

## [0.1.1] - 2026-07-02

### Added

- Stage 4 confidence decay and early exit in foresight simulator.
- Weighted cumulative risk/cost in plan evaluator.

## [0.1.0] - 2026-06-15

### Added

- Initial release with event-sourced memory, task orchestration, and MCP stdio server.
- FastMCP tool definitions for events, tasks, conflicts, sessions, snapshots, and UI views.
- Deterministic replay, scenario generation, counterfactual reasoning, and decision pipelines.
- Observability dashboards, workflow traces, and system metrics.
