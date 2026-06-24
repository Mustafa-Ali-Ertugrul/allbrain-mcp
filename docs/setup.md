# Setup

AllBrain MCP speaks stdio, so you connect it by pointing your MCP client at the server command.

## 1) Start the server

```powershell
uv run allbrain start --project . --agent codex
```

## 2) Codex

Use this command in Codex MCP config:

```powershell
<repo>\.venv\Scripts\python.exe -m allbrain.cli.main start --project <repo> --agent codex --db-path <repo>\.allbrain-codex.db
```

## 3) Claude Code

Use the same server command, but change the agent name:

```powershell
<repo>\.venv\Scripts\python.exe -m allbrain.cli.main start --project <repo> --agent claude-code --db-path <repo>\.allbrain-claude.db
```

## 4) Antigravity

Put the same stdio command into Antigravity's raw MCP config.

## Notes

- Use one shared project root per workspace.
- Use one DB file if you want all agents to share memory.
- Use separate DB files if you want isolated experiments.
