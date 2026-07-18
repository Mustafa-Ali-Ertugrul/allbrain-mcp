# Sprint 75 — SDK Typed Methods (Prompts/Resources) + Inventory Verification

## Goal

Complete the Sprint 71/72 SDK typed-methods work that was deferred, and add an
operational inventory-verification path so the static resource/prompt registry
can be checked against a live MCP server. This also restores SDK prompt/resource
client tests that PR #38 had removed because the fake test client lacked the
required methods.

## Architecture

`AllBrainClient` (`packages/allbrain-sdk/src/allbrain_sdk/client.py`) was
extended with typed methods over the FastMCP resource/prompt API:

- Prompt methods: `resume_project_prompt(limit=5000)`, `task_handoff_prompt`,
  `investigate_conflict_prompt(session_id)` → `PromptResult`.
- Resource methods: `project_resume_raw()`, `tasks_graph_raw()`,
  `git_fingerprint_raw()`, `session_summary(session_id)`, `event_by_id(event_id)`
  → `ResourceRead`.
- Models added: `ResourceRead`, `ResourceDescriptor`,
  `ResourceTemplateDescriptor`, `PromptMessage`, `PromptResult`,
  `PromptDescriptor` (plus existing typed tool results).
- `get_prompt` message parsing fixed: `result.messages` items are
  `PromptMessage(role, content=TextContent)` — `content` is `TextContent` whose
  `.text` holds the string, not a nested `.content`.

`src/allbrain/ops/inventory.py` provides the verification surface:

- `RESOURCE_INVENTORY` / `PROMPT_INVENTORY` static registries.
- `build_resource_inventory()` / `build_prompt_inventory()` helpers.
- `verify_inventory_against_server(client)` — drives the async SDK via
  `asyncio.run`, compares the static registry against the live server's
  `list_resources` / `list_resource_templates` / `list_prompts`, and returns a
  structured `{ok, resources:{matched,missing,extra}, prompts:{...}}` report
  (failures reported as `ok=False`, never raised).
- CLI `doctor --inventory` (and related) surfaces the inventory/verification.

## Files

| File | Change |
|------|--------|
| `packages/allbrain-sdk/src/allbrain_sdk/client.py` | 8 prompt/resource typed methods; `get_prompt` parsing fix |
| `packages/allbrain-sdk/src/allbrain_sdk/models.py` | `ResourceRead`, `PromptMessage`, `PromptResult`, `PromptDescriptor`, `ResourceDescriptor`, `ResourceTemplateDescriptor` |
| `packages/allbrain-sdk/src/allbrain_sdk/__init__.py` | export new models |
| `packages/allbrain-sdk/README.md` | typed-method usage docs |
| `src/allbrain/ops/inventory.py` | `verify_inventory_against_server` |
| `src/allbrain/ops/__init__.py` | export inventory helpers |
| `src/allbrain/cli/main.py` | `doctor --inventory` / verification wiring |
| `src/allbrain/security/redaction.py` | small fix |
| `src/allbrain/server/tools/projections.py` | small fix |
| `tests/sdk/test_client.py` | `FakeMCPClient` expanded: `read_resource`, `get_prompt`, `list_resources`, `list_resource_templates`, `list_prompts` |
| `tests/sdk/test_prompts_client.py` | restored (4 tests) |
| `tests/sdk/test_resources_client.py` | restored (5 tests) |
| `tests/test_ops_inventory.py` | new (4 tests) |
| `tests/test_cli_doctor_inventory.py` | new (4 tests) |
| `docs/sprints/sprint72_sdk_resources_prompts_client.md` | tracked from prior sprint work |

## Decisions

- Single connected `AllBrainClient`; no second stdio transport for verification.
- Inventory stays static (Sprint 71 decision); runtime verification compares it
  against the live server rather than generating it dynamically.
- `FakeMCPClient` was expanded (not replaced) so all existing tool-call tests
  keep working; `read_resource`/`get_prompt` return `SimpleNamespace` shapes that
  mirror the real FastMCP client so `client.py` parses them identically.
- `verify_inventory_against_server` swallows exceptions and returns `ok=False`
  with an `error` field, so `doctor` can report mismatches without crashing.

## Verification

- `ruff format --check` / `ruff check`: clean
- `pyright` (SDK package): 0 errors
- `scripts/check_complexity.py`: no new/worsened/stale debt
- Full suite: 2781 passed, 3 skipped
- All CI checks green on PR #39 (Lint, Security, Test, broker/PostgreSQL/installer
  contracts, Kilo Code Review).

## Commits

`df85a5a feat: Sprint 75 — SDK typed methods (prompts/resources) + inventory verification`
`238b5a2 test: Sprint 75 — SDK client/prompt/resource tests + FakeMCPClient expansion`
(Merged via PR #39 → `0ae20ae`)
