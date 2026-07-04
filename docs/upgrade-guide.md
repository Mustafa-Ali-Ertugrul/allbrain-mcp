# Upgrade Guide

## Versioning

AllBrain MCP uses [Semantic Versioning](https://semver.org/):

- **Patch** (`0.2.0` → `0.2.1`): bug fixes, internal refactors, no CLI or tool API changes
- **Minor** (`0.2.0` → `0.3.0`): new tools, CLI commands, or profiles; backward-compatible
- **Major** (`0.2.0` → `1.0.0`): breaking changes to tool signatures, CLI commands, or storage format

Pre-1.0 versions use the minor number for breaking changes (e.g., `0.3.0` could include migration steps).

## Before upgrading

1. **Back up your database:**
   ```shell
   allbrain backup
   ```
   This creates a timestamped copy at `~/.allbrain/allbrain.db.bak.<timestamp>`.

2. **Check the changelog** for any manual migration steps.

3. **Test in an isolated copy** if you run multiple agents against the same database.

## Upgrade via PyPI

```shell
pipx upgrade allbrain-mcp
```

Or if you use `uvx`:

```shell
uvx allbrain-mcp@latest install --codex --verify
```

The `install` command updates the client configuration to the new version path.

## Upgrade from source

```shell
git pull
uv sync
./scripts/install-mcp.sh --all --verify
```

## After upgrading

1. Restart your MCP clients (Codex, Claude Code, etc.).
2. Run `allbrain doctor` to confirm the server starts and the database is healthy.
3. Run `allbrain verify` for a product-level connectivity check.

## Rollback

### PyPI install

```shell
pipx install allbrain-mcp==0.2.0
allbrain-mcp install --codex
```

### Source install

```shell
git checkout v0.2.0
uv sync
./scripts/install-mcp.sh --all
```

### Database rollback

AllBrain does not apply automatic destructive migrations. If a version introduces an incompatible schema change, the upgrade guide for that version will include explicit migration or rebuild instructions.

To revert to a backup:

```shell
# Stop all agents using the database
# Replace with your backup
cp ~/.allbrain/allbrain.db.bak.<timestamp> ~/.allbrain/allbrain.db
# Restart clients
```

## Migration notes by version

### 0.2.0 — First public release

- Initial event store schema (SQLite)
- Tool profiles: `full`, `core`
- CLI commands: `install`, `start`

### 0.3.0 (planned)

- Expanded tool profiles: `minimal`, `memory`, `collaboration`, `reasoning`
- CLI commands: `verify`, `status`, `backup`, `doctor`, `uninstall`
- No storage migration required.

## Semver policy for the event store

- Adding a new event type or reducer method is NOT a breaking change (event store is append-only).
- Changing the primary key scheme or stream-ordering algorithm IS a breaking change.
- Dropping a table or column without a migration window IS a breaking change.
