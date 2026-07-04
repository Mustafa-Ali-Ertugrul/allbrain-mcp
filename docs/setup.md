# Installation and MCP setup

This guide connects AllBrain MCP to the major MCP-capable coding clients.

All four clients start the same local stdio MCP server. By default, AllBrain stores shared state in:

```text
~/.allbrain/allbrain.db
```

Because the clients use the same project path and database, events written by one agent can be resumed by another.

## Requirements

- Git
- Python 3.12 or newer
- `uv`
- at least one supported MCP client

Check the required commands:

```powershell
git --version
python --version
uv --version
```

Install `uv` if it is missing:

### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### macOS and Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the terminal after installing `uv`.

## Clone and prepare AllBrain

```powershell
git clone https://github.com/Mustafa-Ali-Ertugrul/allbrain-mcp.git
cd allbrain-mcp
uv sync
```

Confirm that the server starts:

```powershell
uv run allbrain start --project . --agent setup-test
```

The server waits for MCP messages over stdio. Seeing it remain open is expected. Press `Ctrl+C` after the check.

## Automatic setup

### Windows

Run from the repository root:

```powershell
.\scripts\install-mcp.ps1 -All
```

Install only selected clients (the same pattern works for every name below):

```powershell
.\scripts\install-mcp.ps1 -Codex
.\scripts\install-mcp.ps1 -Claude
.\scripts\install-mcp.ps1 -OpenCode
.\scripts\install-mcp.ps1 -Antigravity
.\scripts\install-mcp.ps1 -VSCode -Cursor -Gemini -Kiro
```

After installation, completely restart the affected clients.

### macOS and Linux

Run from the repository root:

```bash
./scripts/install-mcp.sh --all
```

Install only selected clients:

```bash
./scripts/install-mcp.sh --codex
./scripts/install-mcp.sh --claude
./scripts/install-mcp.sh --opencode
./scripts/install-mcp.sh --antigravity
./scripts/install-mcp.sh --vscode --cursor --gemini --kiro
```

After installation, completely restart the affected clients.

### Supported automatic targets

| Family | Clients |
|---|---|
| CLI agents | Codex, Claude Code, OpenCode, Gemini CLI, Kiro CLI |
| Editors/IDEs | VS Code, Cursor, Windsurf, Zed, Kiro |
| Desktop agents | Claude Desktop, Antigravity |

The installer uses absolute repository and project paths, merges the `allbrain` entry without deleting other MCP servers, and points every client at the shared database by default. Add `--isolate` (or `-Isolate` on Windows) only when cross-client memory is not desired.

For another standards-compliant MCP client, use this universal stdio server entry and substitute absolute paths:

```json
{
  "mcpServers": {
    "allbrain": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/allbrain-mcp", "allbrain", "start", "--project", "/path/to/project", "--agent", "custom-client", "--db-path", "/home/user/.allbrain/allbrain.db"]
    }
  }
}
```

## Codex

The repository includes `.codex/config.toml`:

```toml
[mcp_servers.allbrain]
command = "uv"
args = ["run", "allbrain", "start", "--project", ".", "--agent", "codex"]
cwd = "."
startup_timeout_sec = 20
tool_timeout_sec = 120
enabled = true
required = true
```

Open the cloned repository as the Codex workspace and restart Codex. `allbrain` should appear in the MCP tools list.

For a global installation, copy the `[mcp_servers.allbrain]` block into:

```text
Windows: %USERPROFILE%\.codex\config.toml
macOS/Linux: ~/.codex/config.toml
```

For a global entry, replace `.` with the absolute repository path.

## Claude Code

The repository includes `.mcp.json`:

```json
{
  "mcpServers": {
    "allbrain": {
      "command": "uv",
      "args": [
        "run",
        "allbrain",
        "start",
        "--project",
        ".",
        "--agent",
        "claude-code"
      ],
      "cwd": "."
    }
  }
}
```

Open Claude Code from the repository root:

```powershell
cd allbrain-mcp
claude
```

Accept the project MCP server if Claude asks for trust or approval. Use Claude Code's MCP command or tools view to confirm that `allbrain` is connected.

## OpenCode

The repository includes `.opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "allbrain": {
      "type": "local",
      "command": [
        "uv",
        "run",
        "allbrain",
        "start",
        "--project",
        ".",
        "--agent",
        "opencode"
      ],
      "cwd": ".",
      "enabled": true
    }
  }
}
```

Start OpenCode from the repository:

```powershell
cd allbrain-mcp
opencode
```

Open the MCP section and confirm that `allbrain` is enabled.

If your OpenCode version does not read project-local configuration, merge the `allbrain` entry into:

```text
Windows: %USERPROFILE%\.config\opencode\opencode.json
macOS/Linux: ~/.config/opencode/opencode.json
```

## Antigravity

Antigravity reads its MCP servers from:

```text
Windows: %USERPROFILE%\.gemini\antigravity\mcp_config.json
macOS/Linux: ~/.gemini/antigravity/mcp_config.json
```

On Windows, the installer safely adds the `allbrain` entry while preserving existing MCP servers:

```powershell
.\scripts\install-mcp.ps1 -Antigravity
```

For manual setup, add this entry under `mcpServers`, replacing `/absolute/path/allbrain-mcp`:

```json
{
  "mcpServers": {
    "allbrain": {
      "command": "uv",
      "args": [
        "run",
        "allbrain",
        "start",
        "--project",
        "/absolute/path/allbrain-mcp",
        "--agent",
        "antigravity",
        "--db-path",
        "/absolute/path/allbrain-mcp/.allbrain/allbrain.db"
      ],
      "cwd": "/absolute/path/allbrain-mcp",
      "env": {},
      "timeout": 120000
    }
  }
}
```

For per-agent isolation, replace `allbrain.db` with `<agent>.db` (e.g. `antigravity.db`).

Restart Antigravity and check the MCP management page for `allbrain`.

## Verify the connection

Ask the client to call:

```text
list_events
```

Then create an event:

```text
Call save_event with:
type = "task_started"
payload = {"task": "Verify AllBrain MCP"}
```

Finally call:

```text
resume_project
```

The resumed state should include `Verify AllBrain MCP`.

## Verify shared multi-agent memory

1. In Codex, save a `task_started` event.
2. In Claude Code, call `list_events`.
3. In OpenCode or Antigravity, call `resume_project`.

All clients should see the same project history.

Project identity is based on the canonical project path. Make sure every client points to the same repository directory.

## Shared versus isolated databases

By default, all clients use the global shared database:

```text
~/.allbrain/allbrain.db
```

This is the easiest shared-memory setup: every agent writes to and reads from the same database.

### `--isolate` flag (recommended for isolation)

The install scripts accept a `--isolate` flag that assigns a separate database per agent:

```powershell
# Windows — per-agent databases
.\scripts\install-mcp.ps1 -All -Isolate
```

```bash
# macOS / Linux
./scripts/install-mcp.sh --all --isolate
```

When `--isolate` is set, each agent config receives a `--db-path` argument pointing to an agent-specific file:

| Agent | Database path |
|-------|---------------|
| Codex | `~/.allbrain/codex.db` |
| Claude Code | `~/.allbrain/claude-code.db` |
| OpenCode | `~/.allbrain/opencode.db` |
| Antigravity | `~/.allbrain/antigravity.db` |

This makes isolation explicit and centrally managed by the installer instead of requiring manual `--db-path` edits across multiple config files.

### Manual isolation

To isolate a single client manually, add `--db-path` to its config:

```text
--db-path /path/to/client-specific.db
```

### Important

- Do **not** use different database paths when you expect agents to share memory.
- Re-run the installer with or without `--isolate` to switch between shared and isolated modes — config files are regenerated.
- AllBrain database paths use forward slashes (`/`) in generated config files for cross-platform consistency.

## Troubleshooting

### `allbrain` does not appear

- Restart the client completely.
- Confirm that the config file is in the correct location.
- Open the repository itself, not its parent folder.
- Validate that `uv` is available in a fresh terminal.

### `uv` or `allbrain` cannot be found

Run:

```powershell
uv sync
uv run allbrain --help
```

Use the absolute path to `uv` in the MCP config if the GUI client has a different `PATH`.

### Server starts and immediately disconnects

Run the exact MCP command manually and inspect stderr:

```powershell
uv run allbrain start --project . --agent debug
```

### Agents cannot see each other's events

- Check that every config uses the same `--project` path.
- Check that every config uses the same database.
- Avoid opening the same repository through different symlink or junction paths.

### Windows paths with spaces or non-ASCII characters

Keep command and path values as separate JSON/TOML arguments. Do not build one quoted command string.

If a client still fails, clone the repository to a short path such as:

```text
C:\allbrain-mcp
```

## Security notes

- AllBrain runs locally and writes to SQLite.
- Review MCP configuration before trusting a cloned repository.
- Do not commit API keys or personal database files.
- `.allbrain-*.db` files are ignored by Git.

### Vulnerability scanning

Scan the dependency tree for known vulnerabilities with `pip-audit`:

```bash
uv run --group dev pip-audit
```

The project uses `pip-audit` (PyPA/Google-backed) instead of `safety` to avoid license restrictions and dependency conflicts. To run `safety` in an isolated sandbox without polluting the project venv:

```bash
uvx safety check
```
