# AllBrain MCP v0.2.3 Upgrade & Compatibility Guide

This guide details the steps to upgrade from v0.2.2 to v0.2.3, along with environment constraints and compatibility metrics.

## 1. Compatibility Matrix

| Environment | Supported Version | Notes |
|-------------|-------------------|-------|
| **Python** | `3.12` to `3.13` | CI validates against Python 3.13.14 |
| **OS** | Windows, macOS, Linux | Platform-agnostic (Alembic/SQLModel) |
| **SQLite** | `>= 3.35.0` | Required for window functions and returning clause |
| **Clients** | Codex, Claude Code, Cursor, VS Code, OpenCode, Zed, Windsurf, Kiro | Standard stdio protocol |

## 2. Upgrade Steps (v0.2.2 → v0.2.3)

### Environment Variable Update
The path-traversal project root filter has been standardized.
* **Deprecated:** `ALLOWED_PROJECT_ROOTS`
* **New:** `ALLBRAIN_ALLOWED_PROJECT_ROOTS`
* *Action:* Rename your environment variable to `ALLBRAIN_ALLOWED_PROJECT_ROOTS`. If you keep the legacy name, the server will emit a `DeprecationWarning`.

### Configuration Update
For clients utilizing absolute database configurations (e.g. Codex `.codex/config.toml` or Cursor `.cursor/mcp.json`), ensure the DB path points to the standardized central location `~/.allbrain/allbrain.db` to prevent local project database duplication.

### Migration Steps
No manual database schema migrations are required. The Alembic upgrade will stamp the database schema automatically upon server start.
