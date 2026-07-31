# Qwen Architectural Review — Audit Results

Date: 2026-07-31
Scope: Fact-check of an external static architectural review against the repository at HEAD `39aff1d` plus the working tree.

## Verdict summary

| Review claim | Verdict | Evidence |
|---|---|---|
| SV-5: `tools/__init__.py` hardcodes 18 module imports | **Wrong (already fixed)** — dynamic discovery via `pkgutil.iter_modules` + `_ProfiledToolRegistrar` | `server/tools/__init__.py:71-88`, commit `39aff1d` |
| SEC-5: `agents/safety.py` (24 patterns) diverges from `_prompt_rules.py` (14 patterns) | **Wrong** — `agents/safety.py` does not exist; single source `security/_prompt_rules.py` imported by `input_guard.py` (now 22 patterns) | `security/` listing, `security/input_guard.py:11` |
| X-1: 73+ shim files at package root | **Wrong** — 13 shims at `src/allbrain` root; 14 shim-like files (<12 lines) in the whole package | `Get-ChildItem src\allbrain` |
| X-5: `docs/architecture.md` returns 404 | **Wrong** — `docs/ARCHITECTURE.md` exists and README links it correctly | `README.md:218` |
| C-1: `StateEngine.build_state()` untyped dict access | **Wrong/weak** — signature is `context: dict[str, Any]`, uses `.get()` | `core/state_engine.py:14-15` |
| 426 commits | **Off by 5** — 421 at HEAD | `git rev-list --count HEAD` |
| C-3: `Session.last_heartbeat_at` defaults to `utc_now` | **True** | `models/entities.py:30` |
| C-4: `delta_state` manually overridden for 8 fields | **True** (intentional, commented) | `core/state_engine.py:48-56` |
| C-2: `EventReducer.ingest_events` builds a new `StateEngine` per call | **True** | `core/state_engine.py:61` |
| SV-1: lifecycle uses `asyncio.create_task` | **True** | `server/lifecycle.py:35-36` |
| SV-2: two separate locks in context | **True** (`_session_lock` RLock + `_count_lock`) | `server/context.py:46-47` |
| SV-3: duplicate tool error decorators | **True — fixed this session** (shared `_client_error_result`, `_invoke` reused) | `server/tools/decorators.py` |
| SV-4: `renew`/`complete`/`fail` used read sessions while `claim` used write | **True for HEAD — fixed this session** (all four now `open_write_session`; `renew` validates TTL 30..3600) | `server/queueing.py:92-278` |
| SV-6: `import asyncio` inside `_is_coroutine` | **True — fixed this session** (moved to module top) | `server/tools/decorators.py` |
| SEC-1: `_MAX_SANITIZE_DEPTH` frozen at module load | **True — fixed this session** (runtime reads env lazily; constant kept for imports) | `security/redaction.py:20-37,288-302` |
| SEC-2: ReDoS heuristic guard exists | **True** | `security/redaction.py:14-17,64-68` |
| SEC-3: mutable module-level `SECRET_PATTERNS` | **True** (by design; `reload_secret_patterns()` exists) | `security/redaction.py:120-128` |
| SEC-4: rate limiter is process-local | **True** (in-memory `SlidingWindowCounter`, threading lock) | `security/rate_limit.py` |
| S-3: `history_repair.py` suspicion | **Speculative** — offline `repair-history` CLI tool merging source DBs and closing stale sessions; no runtime event mutation | `storage/history_repair.py`, `cli/main.py:335-357` |
| M-2: gitbrain uses GitPython | **True** (path is `domains/memory/gitbrain`, not collaboration) | `domains/memory/gitbrain/parser.py:11-12` |
| X-6: fastmcp pinned `>=3.4.2,<3.5` | **True** | `pyproject.toml` |
| X-7: `weights_adapated` alias | **True** | `events/schemas.py:9` |
| CLI-1: 3 console script aliases | **True** | `pyproject.toml [project.scripts]` |
| T-1: coverage threshold / current % | **Partial** — actual coverage 86.47% (claimed 86.54%); `fail_under = 84` | `pytest --cov` run, `pyproject.toml` |
| T-2: pyright scoped to a few files | **True** (models, security, 4 files, SDK) | `pyproject.toml [tool.pyright]` |
| T-4: bandit `-ll`, B311 skipped | **True** | `pyproject.toml`, `.github/workflows/ci.yml:41` |
| T-5: stress p95 budget 0.700s | **True** | `.github/workflows/stress.yml:16` |
| 53 MCP tools, profile sizes (minimal 3 / memory 5 / collaboration 10 / reasoning 14 / core 11) | **True** | `server/tools/__init__.py:27-58`, 53 `@mcp.tool` registrations |
| `test_redaction_fail_closed.py` 12 tests, `test_gitbrain_rce_sandbox.py` 7 tests | **True** | test files |

## Issues the review missed (fixed in working tree)

1. Six user contract tests had never run green (20 failures fixed): `test_prompt_rules_phase_f`, `test_quarantine`, `test_queue_renew_complete_fail`, `test_repository_integrity_audit`, `test_save_event_agent_id`, `test_session_report_n1`.
2. Quarantine promote cache invalidation bug (`server/context.py` — `_promoted_ids` now reset to `None`).
3. Queueing `renew`/`complete`/`fail` lacked write locking and TTL validation.
4. `build_session_report` N+1 query loop (`server/tools/sessions.py` — batched `session_event_counts` + `latest_session_summaries`).
5. No integrity verification tool — added `repository.verify_integrity()` + `doctor --verify-integrity` hash-chain check.
6. Prompt injection patterns were 14, expanded to 22 in `security/_prompt_rules.py`.
7. Migration `0004_integrity_meta_columns.py` existed untracked (not in git).
8. Test isolation bug: `tests/test_decorators_exception_handling.py` left a stubbed `sys.modules["allbrain.server.tools.decorators"]` behind, making `test_error_masking` order-dependent — fixed by restoring the module.

## Verification commands

```
.venv\Scripts\python.exe -m pytest tests\ -q                # 3142 passed, 5 skipped
.venv\Scripts\python.exe -m pytest tests\ -q --cov=allbrain # 86.47%, fail_under 84 OK
.venv\Scripts\ruff.exe check src\ tests\                    # clean
```
