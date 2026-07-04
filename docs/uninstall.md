# Uninstall

This guide removes AllBrain MCP from your system completely — the repository, virtual environment, shared database, and all client MCP registrations.

## Remove MCP client registrations

Before deleting files, remove the `allbrain` entry from every MCP client that loaded it.

### Codex

Open `~/.codex/config.toml` (or `%USERPROFILE%\.codex\config.toml` on Windows) and remove the `[mcp_servers.allbrain]` section.

If you used the project-local `.codex/config.toml`, the entry disappears when you delete the repository.

### Claude Code

Open `.mcp.json` (project-local or global at `~/.mcp.json`) and delete the `allbrain` entry from `mcpServers`.

### OpenCode

Open `opencode.json` (project-local `opencode.json` or global at `~/.config/opencode/opencode.json`) and remove the `allbrain` block from `mcp`.

### Antigravity

Open the MCP config file:

- **Windows**: `%USERPROFILE%\.gemini\antigravity\mcp_config.json`
- **macOS/Linux**: `~/.gemini/antigravity/mcp_config.json`

Remove the `allbrain` entry from `mcpServers`.

### VS Code, Cursor, Windsurf, Zed, Kiro

Open the editor's MCP configuration file and remove the `allbrain` entry from `mcpServers`.

Typical locations:

| Client | Config file |
|---|---|
| VS Code / Cursor | `.vscode/mcp.json` or global `mcp.json` |
| Windsurf | `.codeium/windsurf/mcp_config.json` |
| Zed | `~/.config/zed/mcp.json` |
| Kiro | `.kiro/settings/mcp.json` or global equivalent |

### Gemini CLI

Open the Gemini CLI configuration and remove the `allbrain` entry. The location depends on the CLI version; check `~/.gemini/` for relevant config files.

### Kiro CLI

Remove the `allbrain` entry from `.kiro/settings/mcp.json` or the global equivalent.

## Delete the repository

```bash
rm -rf allbrain-mcp
```

On Windows:

```powershell
Remove-Item -Recurse -Force allbrain-mcp
```

## Remove the database (optional)

The shared database is kept after deleting the repository so that data survives reinstallation. To remove it:

```bash
rm -rf ~/.allbrain
```

On Windows:

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.allbrain"
```

This deletes all stored events, sessions, and configuration data.

## Remove Python dependencies (optional)

If you no longer need the project's virtual environment, delete it:

```bash
rm -rf .venv
```

The virtual environment is inside the repository and is removed with the repository in the step above.

## Remove the uv cache (optional)

```bash
uv cache clean
```

## Verify removal

Confirm that no `allbrain` entries remain:

```bash
grep -r "allbrain" ~/.mcp.json ~/.codex/config.toml ~/.config/opencode/opencode.json 2>/dev/null || echo "No references found"
```

On Windows:

```powershell
Select-String -Path "$env:USERPROFILE\.mcp.json", "$env:USERPROFILE\.codex\config.toml", "$env:USERPROFILE\.config\opencode\opencode.json" -Pattern "allbrain" 2>$null
```

If any references remain, remove them manually using the client-specific steps above.
