# Sprint 72 — AllBrain SDK: Resources & Prompts Client Surface

## Goal

Sprint 71 added read-only MCP **resources** (`project://resume`, `tasks://graph`,
`git://fingerprint`, `session://{session_id}/summary`, `event://{event_id}`) and
reusable **prompts** (`resume_project`, `task_handoff`, `investigate_conflict`)
to the server. Sprint 72 closes the loop by exposing those surfaces through the
typed SDK client and a `doctor` verification path, so external agents can read
project state and generate workflow prompts without calling tools.

## Architecture

The `AllBrainClient` already owned stdio lifecycle and tool calls via
`self._client.call_tool(...)`. Sprint 72 extends it with the FastMCP client's
native resource/prompt API (FastMCP 3.4.2):

- `read_resource(uri)` → `ResourceRead` (text or blob)
- `get_prompt(name, **arguments)` → `PromptResult` (`list[PromptMessage]`)
- `list_resources`, `list_resource_templates`, `list_prompts` → typed descriptors
- Typed shortcuts per server resource/prompt (e.g. `project_resume_raw`,
  `session_summary`, `task_handoff_prompt`)

Resource content is returned as serialized JSON text (resources are read-only and
the server emits `json.dumps(..., sort_keys=True, default=str)`). Prompt messages
are wrapped in `PromptMessage(role, content)`; non-text content is JSON-encoded.

`doctor --inventory` prints the static inventory; `doctor --verify` launches a
live `AllBrainClient` (agent `cli-verify`) and compares the static inventory
against the running server via `verify_inventory_against_server`, exiting
non-zero on mismatch.

## Files

| File | Change |
|------|--------|
| `packages/allbrain-sdk/src/allbrain_sdk/models.py` | `ResourceRead`, `ResourceDescriptor`, `ResourceTemplateDescriptor`, `PromptMessage`, `PromptResult`, `PromptDescriptor` |
| `packages/allbrain-sdk/src/allbrain_sdk/client.py` | resource/prompt methods + typed shortcuts |
| `packages/allbrain-sdk/src/allbrain_sdk/__init__.py` | export new models |
| `src/allbrain/ops/inventory.py` | `verify_inventory_against_server` |
| `src/allbrain/cli/main.py` | `doctor --inventory` / `--verify` |
| `tests/sdk/test_client.py` | extended with resource/prompt tests |
| `tests/sdk/test_resources_client.py` | new |
| `tests/sdk/test_prompts_client.py` | new |
| `tests/test_cli_doctor_inventory.py` | new |

## Decisions

- Reuse a single connected `AllBrainClient`; no second stdio transport.
- Envanter statik kalır (Sprint 71 kararı); doğrulama runtime'da canlı ile karşılaştırma yapar.
- Prompt non-text content fallbacks to `json.dumps` to keep `PromptMessage.content` a `str`.
- `verify_inventory_against_server` drives the async SDK via `asyncio.run` and
  reports failures as `ok=False` rather than raising.

## Verification

- `ruff format --check` / `ruff check`: clean
- `pyright` (SDK package): 0 errors
- `pytest tests/sdk tests/test_mcp_resources.py tests/test_mcp_resources_register.py tests/test_cli_doctor_inventory.py`: all pass
