# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
