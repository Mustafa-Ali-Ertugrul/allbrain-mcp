# Contributing to AllBrain MCP

## Development setup

```powershell
uv sync --group dev
```

Confirm the CLI starts:

```powershell
uv run allbrain --help
```

## Local checks

Run the narrowest relevant check first, then the full local CI before publishing changes:

```powershell
make lint
make security
make test
make ci-local
```

`make lint` runs Ruff, format checks, complexity checks, and architecture boundary checks. The lint target is fail-closed; do not bypass it with `--exit-zero` or `|| true`.

Audit development and optional dependencies with:

```powershell
uv run --group dev pip-audit
```

The project uses `pip-audit`, not `safety`, for its supported dependency-vulnerability workflow. `make security` separately runs Bandit against first-party source code; accepted findings and reporting guidance are documented in [SECURITY.md](SECURITY.md).

## Testing expectations

- Bug fixes should include a regression test that fails before the fix.
- Refactors should preserve behavior and keep existing tests green.
- New memory projections should be covered by `MemoryBuilder` tests and include deterministic IDs, tags, timestamps, and source event IDs.
- New pipeline steps should be covered by unit tests under `tests/runtime_core/` and at least one integration or characterization test when behavior changes.

## Architecture rules

- Domain packages must not import `allbrain.server` or storage adapters directly.
- The server layer may call domain packages, but domain packages should remain replayable and deterministic.
- Runtime pipeline orchestration lives under `src/allbrain/runtime_core/`.
- MCP tool implementation code lives under `src/allbrain/server/tools/`.
- Event payload keys may be added, but existing payload keys should not be removed or renamed in a breaking way.

## Documentation expectations

- Update `CHANGELOG.md` under `[Unreleased]` for user-visible changes.
- Update `docs/ARCHITECTURE.md` when package boundaries or runtime flow change.
- Update `README.md` status items when test counts or setup instructions change.

## Release process

Only maintainers should cut releases.

1. Ensure the worktree contains only intended changes.
2. Run:

   ```powershell
   make ci-local
   ```

3. Bump the version:

   ```powershell
   make bump-patch
   ```

   Use `make bump-minor` or `make bump-major` for larger releases.

4. Review the generated version changes and tag.
5. Push explicitly:

   ```powershell
   git push
   git push --tags
   ```

`make release` runs lint, security, tests, and then performs a patch bump. It does not push to remotes.
