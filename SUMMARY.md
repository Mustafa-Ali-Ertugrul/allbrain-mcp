# AllBrain Security Hardening — Anchored Summary

## Goal
- Fixed all CRITICAL, HIGH, MEDIUM, LOW findings from the pentest results — recursive null-byte validation, regex-based credential env stripping, 5 new secret redaction patterns, 2 prompt-injection pattern fixes, SSH PEM regex bug, and 20+ new tests — all while keeping the full suite green at 1888/1888.

## Constraints & Preferences
- Never break existing tests; fix any broken tests as part of implementation.
- Full test suite must remain green after each change (pre-existing flaky `test_concurrent_save_event_no_deadlock` excluded — SQLite deadlock race).
- Defense-in-depth: validate at both MCP boundary (Pydantic) and storage layer / git subprocess.

## Progress
### Done
- **Phase 0**: Created `bench_write_throughput.py` + `bench_baseline.json` for redaction/perf benchmarks.
- **Phase 1**: Fixed 3 pre-existing test failures — added `agent_id=data.agent_id` to `save_event_impl`; fixed `replay_workflow_impl` (`.workflow_replay()` → `.replay()`, removed extra `.model_dump()`).
- **Phase 2.1**: Created `src/allbrain/security/input_guard.py` with expanded prompt-injection regex patterns; wired `sanitize_user_text` / `sanitize_payload_fields` into `BaseInputModel._sanitize_strings` field validator.
- **Phase 2.2**: Enhanced `security/redaction.py` with field-name based redaction (exact name matching only — `metric_key` etc. are not redacted). Wired `sanitize_payload` in `repository.py._append_event_core`. All 33 redaction/bypass tests pass.
- **Phase 2.3**: Added `BaseInputModel._check_dict_sizes` — 250 KB limit for `payload`, 50 KB for other dict fields.
- **Phase 3.1**: Added `ALLOWED_PROJECT_ROOTS` env var (default `Path.home()`), `PathTraversalError`, and `canonicalize_project_path` validation.
- **Phase 3.2**: GitPython output sanitization — added public `sanitize_text()` to `redaction.py`, applied to status/diff/branch/commit summaries in `GitBrain`. Env sandbox — `safe_git_env()` strips credential vars, `_git_env` context manager replaces `os.environ` for git subprocess calls.
- **Phase 4.1**: Created `src/allbrain/security/rate_limit.py` — `SlidingWindowCounter` (per-key, configurable), wired `check_tool_rate()` into `save_event_impl`, `list_events_impl`, `create_task_impl`, `assign_task_impl`. Defaults: 100 000/min, 1000/sec (configurable via `ALLBRAIN_RATE_LIMIT_RPM` / `ALLBRAIN_RATE_LIMIT_RPS`). 11 unit tests pass.
- **Phase 4.2**: Fixed `SqliteQueue.capabilities()` — changed `"distributed_ready": True` → `False`. Redis and RabbitMQ queues correctly remain `True`.
- **Phase 5.1**: Added `sanitize_valerr_msg()` to `redaction.py` — strips Pydantic `input_value=...` fragments from `ValidationError` messages. Applied to all 49 `except ValidationError` handlers in `app.py` (replaced `error=str(exc)` with `error=sanitize_valerr_msg(str(exc))`).
- **Phase 5.2**: Added major-version upper bounds to all `pyproject.toml` dependencies.
- **Phase 5.3**: Gated `_patch_stdio_newlines_for_windows()` in `cli/main.py` — returns early on `sys.version_info >= (3, 14)`.
- **Phase 5.5**: Replaced all naive `datetime.now()` calls with `datetime.now(timezone.utc)` — `runtime.py` (3), `adapter.py` (2), `scheduler_v1.py` (1). Fixed `_recovery_probe()` to treat legacy naive datetimes as UTC. Fixed `test_scale_audit.py` failure by wrapping `choose_agent` in `OrchestratedResumeEngine._decision_view()` with `try/except ValueError`.
- **Pentest**: 20/26 security tests pass, 6 fail — documented findings with evidence.
- **CRITICAL — Null byte in payload dict**: `_check_null_bytes_recursive()` in `schemas.py`. 5 new tests pass.
- **HIGH — Git env credential leak**: Combined exact denylist + regex `_is_credential_var()`. 4 new tests pass.
- **MEDIUM — Undetected secret types**: 5 new patterns (JWT, SSH, Stripe, Twilio, Google). 7 new tests pass.
- **MEDIUM — Prompt injection FN**: Fixed patterns 10 and 14 in `input_guard.py`. 11 new tests pass.
- **LOW — Field name redaction**: Confirmed as pentest test bug; added doc test. No code change.
- **SSH PEM regex fix**: Footer pattern had `(?:OPENSSH|RSA|EC|DSA|PGP )?` where the trailing space was only inside the `PGP ` alternative, so `OPENSSH` matched without a space, breaking the match. Moved space to outside: `(?:OPENSSH|RSA|EC|DSA|PGP) ?`. Both SSH tests now pass.

### In Progress
- (none)

### Blocked
- (none)

## Key Decisions
- Field-name redaction: exact match only, not suffix.
- Path traversal default root: `Path.home()`.
- Rate limiter: sliding-window counter.
- `_git_env`: replaces `os.environ` with credential-stripped copy.
- `ValidationError` sanitized at 49 return points.
- Dependency bounds: semver major-version pinning.
- Stdio monkey-patch gated by version check.
- Legacy naive datetimes treated as UTC.
- Null byte fix at Pydantic validator layer (not sanitization).
- Git env fix: combined exact + regex denylist.
- SSH pattern: full PEM block via `[A-Za-z0-9+/=\s]*?` body.

## Relevant Files
- `src/allbrain/server/app.py`: 49 `except ValidationError` handlers sanitized.
- `src/allbrain/models/schemas.py`: `BaseInputModel` with recursive null-byte + dict size + input guard.
- `src/allbrain/config.py`: `ALLOWED_PROJECT_ROOTS`, `canonicalize_project_path()`.
- `src/allbrain/gitbrain/parser.py`: `safe_git_env()`, `_is_credential_var()`, `_git_env`.
- `src/allbrain/security/redaction.py`: 13 secret content patterns, field-name redaction, `sanitize_text()`, `sanitize_valerr_msg()`.
- `src/allbrain/security/rate_limit.py`: `SlidingWindowCounter`, `check_tool_rate()`.
- `src/allbrain/security/input_guard.py`: 14 prompt-injection regex patterns + sanitizers.
- `src/allbrain/resume/orchestrated.py`: `_decision_view()` `ValueError` catch.
- `src/allbrain/cli/main.py`: stdio patch gated to <3.14.
- `src/allbrain/orchestrator/scoring/scheduler_v1.py`: UTC datetime fix.
- `src/allbrain/agents/safety.py`: Legacy 6-pattern list; divergence noted.
- `pyproject.toml`: All deps pinned with major-version upper bounds.
- **Test files**: `test_security.py` (43), `test_secret_bypass.py` (26), `test_redaction.py` (16), `test_rate_limit.py` (11), `test_unicode.py` (18), `test_input_guard.py` (11), `test_gitbrain.py` (5), `test_log_injection.py` (9), `test_server.py` (11), `test_storage.py` (6) — all pass.
