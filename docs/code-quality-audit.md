# Code Quality and Architecture Audit

Verified on 2026-07-03 against the working tree. Counts are snapshots, not permanent guarantees.

## Verified inventory

| Measure | Before remediation | Current tree |
|---|---:|---:|
| Python files under `src/` | 625 | 626 |
| Source lines | 45,229 | 45,410 |
| Test files | 242 | 242 |
| Test lines | 26,213 | 26,311 |
| Top-level `allbrain` packages | 82 | 82 |
| Collected tests | 2,090 | 2,093 |
| Full-profile MCP tools | 55 | 55 |
| MCP domain tool modules | 18 | 18 |

The pre-remediation full suite completed with 2,086 passed and 4 broker/PostgreSQL tests skipped because their service URLs were not configured. The current-tree result is recorded after the implementation verification below.

## Reproducible checks

```text
uv run pytest --collect-only -q -n 0
uv run pytest -q
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run python scripts/check_complexity.py
uv run python scripts/check_architecture.py
uv run bandit -c pyproject.toml -r src/ -ll
uv run python scripts/audit_dependencies.py
```

- Ruff includes `BLE`; all broad-exception findings must be narrowed or explicitly justified at an extension/process boundary.
- Before remediation there were 72 textual `except Exception` matches but only 15 actionable BLE001 findings. After remediation there are 68 textual matches and 13 explicit, logged BLE001 boundary waivers.
- Bandit reported no medium/high findings. Dependency audit reported no known vulnerabilities on the verification date; the local package itself is skipped because version 0.1.0 is not published on PyPI.
- The configured branch-coverage fail-under is 75%. A local coverage run exceeded its five-minute command budget, so this audit does not invent or report an uncompleted coverage percentage; CI must supply the completed measurement.

## Corrected architectural findings

- UUIDv7 is an event identity, not a clock-independent global ordering guarantee. Database-assigned, project-local `stream_position` now drives repository cursors and replay ordering.
- `EventRead` is a Pydantic model, not a dataclass. `EventStore` is the minimal append/list runtime protocol; cursor methods are repository APIs.
- Event immutability is an application/repository invariant. Direct database administrators are not technically prevented from issuing updates or deletes.
- Reducer idempotence is covered across many domain tests, but one reducer's `_seen_ids` implementation is not proof for every reducer. Replay constructs fresh reducer instances, so the earlier claim of an unbounded long-lived `CapabilityReducer` leak was not substantiated.
- Package consolidation is a subjective architecture trade-off with a large compatibility cost. No package move is justified by this audit; navigation and bounded-context documentation remain the safer control.
- The empty project `.mcp.json` is intentional: project-scope registration was removed to avoid duplicating user-scope MCP registration.
- Redis and RabbitMQ remain experimental, but they already have real-service acknowledgement/reconnect contracts and deterministic lease/requeue tests. Documentation should not describe them as metadata-only stubs.

## Quality policy

- Python 3.12 is the minimum supported interpreter and receives a full compatibility run; Python 3.13 runs coverage.
- Coverage policy is defined once in `pyproject.toml` at 75%.
- Complexity debt is ratcheted: existing baseline entries may improve or disappear, but new/worsened entries fail CI.
- Event IDs remain stable public UUIDs. `EventRead.stream_position` is additive, and UUID cursors are resolved to their database position without changing the external cursor shape.
