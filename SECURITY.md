# Security policy

## Supported versions

AllBrain MCP is currently pre-1.0. Security fixes are applied to the latest revision on the default branch; older revisions are not maintained as separate security release lines.

## Reporting a vulnerability

Do not publish an exploitable vulnerability in a public issue. Use the repository host's private security-advisory channel when available. Otherwise, contact the maintainers privately and include the affected revision, impact, reproduction steps, and any proposed mitigation. Never include real credentials, private event logs, or personal database files in a report.

## Security checks

Install development dependencies and run both source and dependency checks:

```bash
uv sync --group dev
uv run bandit -c pyproject.toml -r src/ -ll
uv run --group dev pip-audit
```

`pip-audit` is the supported dependency scanner. `safety` is not part of the project environment or CI workflow.

## Dashboard security model

The `allbrain ui` dashboard serves raw event data (prompts, tool arguments, repository context) and is therefore treated as sensitive:

- **Authentication:** every `/api/*` endpoint requires a bearer token. A fresh random token (`secrets.token_urlsafe(24)`) is generated per start and included in the URL printed at startup. Set `ALLBRAIN_DASHBOARD_TOKEN` to pin a fixed token for scripted access. Only `/` (static shell) and `/health` (no data) are reachable without it.
- **CORS:** no cross-origin access by default. `Access-Control-Allow-Origin` is only echoed for origins listed in `ALLBRAIN_DASHBOARD_ALLOWED_ORIGINS` (comma-separated). The bundled page is served same-origin and needs no CORS.
- **Binding:** the default bind is `127.0.0.1`. Binding to a non-loopback interface prints an explicit warning; prefer an SSH tunnel over direct network exposure. There is no TLS — do not expose the dashboard over untrusted networks.
- **Input validation:** `/api/events?limit=` accepts integers in the range 1–1000 and returns 400 for anything else.

## Accepted findings and boundaries

- Bandit rule `B311` is skipped in `pyproject.toml`. The flagged pseudo-random choices are used for simulations and heuristics, not for secrets, tokens, identifiers, authentication, or other cryptographic decisions. Security-sensitive randomness must use Python's `secrets` module.
- The default transport is local stdio. Treat MCP configuration as executable configuration and review it before trusting a cloned repository.
- SQLite database files may contain agent prompts, tool arguments, repository context, and event history. Keep them outside version control, restrict filesystem access, and do not attach them to public bug reports.
- Rate limiting is an in-process runaway-loop guard, not a network security boundary. Each server process maintains its own counters.
- AllBrain records and replays agent activity; it does not sandbox tools or make untrusted tool execution safe.
- Sessions finalized by a hung ("zombie") process are defended at the storage layer: terminal session rows can never be resurrected by a late heartbeat, and finalization re-reads the authoritative row to avoid duplicate summaries. If a git-remote feature (clone/fetch/pull) is ever added, URL/branch arguments must pass an allowlist/pattern validation before reaching GitPython.
