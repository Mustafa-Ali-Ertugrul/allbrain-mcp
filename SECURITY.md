# Security policy

## Supported versions

AllBrain MCP is currently pre-1.0. Security fixes are applied to the latest revision on the default branch; older revisions are not maintained as separate security release lines.

## Reporting a vulnerability

Do not publish an exploitable vulnerability in a public issue. Use the repository host's private security-advisory channel when available. Otherwise, contact the maintainers privately and include the affected revision, impact, reproduction steps, and any proposed mitigation. Never include real credentials, private event logs, or personal database files in a report.

## Security checks

Install development dependencies and run both source and dependency checks:

```bash
uv sync --extra dev
uv run bandit -c pyproject.toml -r src/ -ll
uv run --extra dev pip-audit
```

`pip-audit` is the supported dependency scanner. `safety` is not part of the project environment or CI workflow.

## Accepted findings and boundaries

- Bandit rule `B311` is skipped in `pyproject.toml`. The flagged pseudo-random choices are used for simulations and heuristics, not for secrets, tokens, identifiers, authentication, or other cryptographic decisions. Security-sensitive randomness must use Python's `secrets` module.
- The default transport is local stdio. Treat MCP configuration as executable configuration and review it before trusting a cloned repository.
- SQLite database files may contain agent prompts, tool arguments, repository context, and event history. Keep them outside version control, restrict filesystem access, and do not attach them to public bug reports.
- Rate limiting is an in-process runaway-loop guard, not a network security boundary. Each server process maintains its own counters.
- AllBrain records and replays agent activity; it does not sandbox tools or make untrusted tool execution safe.
