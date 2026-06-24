# Setup

AllBrain MCP speaks stdio, so you connect it by pointing your MCP client at the server command.

## Fast path

From the repo root:

```powershell
.\scripts\install-mcp.ps1 -All
```

Then restart Codex, Claude Code, OpenCode, and Antigravity.

## 1) Start the server

```powershell
uv run allbrain start --project . --agent codex
```

## 2) Codex

Codex uses `.codex/config.toml` in the repo:

```powershell
uv run allbrain start --project . --agent codex
```

## 3) Claude Code

Claude Code uses `.mcp.json` in the repo:

```powershell
uv run allbrain start --project . --agent claude-code
```

## 4) OpenCode

OpenCode uses `.opencode/opencode.json` in the repo:

```powershell
uv run allbrain start --project . --agent opencode
```

## 5) Antigravity

Antigravity uses `~/.gemini/antigravity/mcp_config.json`. The installer writes it for you.

## Notes

- Use one shared project root per workspace.
- Use one DB file if you want all agents to share memory.
- Use separate DB files if you want isolated experiments.
