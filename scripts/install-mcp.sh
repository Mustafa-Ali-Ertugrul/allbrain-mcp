#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# install-mcp.sh — AllBrain MCP cross-platform installer (macOS / Linux)
#
# Installs or refreshes MCP client configurations for Codex, Claude Code,
# OpenCode, and Antigravity.
#
# Usage:
#   ./scripts/install-mcp.sh [--all] [--codex] [--claude] [--opencode]
#                            [--antigravity] [--isolate]
#
#   --all           Configure all clients (default when no client flag is given)
#   --codex         Configure only Codex
#   --claude        Configure only Claude Code
#   --opencode      Configure only OpenCode
#   --antigravity   Configure only Antigravity (global config)
#   --isolate       Assign a separate database per agent
#   --help, -h      Show this help message
# ==============================================================================

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALLBRAIN_DIR="$HOME/.allbrain"

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------
INSTALL_CODEX=false
INSTALL_CLAUDE=false
INSTALL_OPENCODE=false
INSTALL_ANTIGRAVITY=false
ISOLATE=false

show_help() {
    sed -n '3,16p' "$0"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)         INSTALL_CODEX=true; INSTALL_CLAUDE=true; INSTALL_OPENCODE=true; INSTALL_ANTIGRAVITY=true; shift ;;
        --codex)       INSTALL_CODEX=true; shift ;;
        --claude)      INSTALL_CLAUDE=true; shift ;;
        --opencode)    INSTALL_OPENCODE=true; shift ;;
        --antigravity) INSTALL_ANTIGRAVITY=true; shift ;;
        --isolate)     ISOLATE=true; shift ;;
        --help|-h)     show_help ;;
        *) echo >&2 "Unknown flag: $1  (use --help for usage)"; exit 2 ;;
    esac
done

# Default: install all when no specific flag is given
if ! $INSTALL_CODEX && ! $INSTALL_CLAUDE && ! $INSTALL_OPENCODE && ! $INSTALL_ANTIGRAVITY; then
    INSTALL_CODEX=true; INSTALL_CLAUDE=true; INSTALL_OPENCODE=true; INSTALL_ANTIGRAVITY=true
fi

# ---------------------------------------------------------------------------
# Prerequisite check
# ---------------------------------------------------------------------------
if ! command -v uv &>/dev/null; then
    echo >&2 "Error: 'uv' package manager not found."
    echo >&2 "Install it first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# ---------------------------------------------------------------------------
# Database path resolver
# ---------------------------------------------------------------------------
resolve_db_path() {
    local agent="$1"
    if [ "$ISOLATE" = true ]; then
        echo "$ALLBRAIN_DIR/$agent.db"
    else
        echo "$ALLBRAIN_DIR/allbrain.db"
    fi
}

echo "AllBrain MCP — installing MCP client configurations"
echo "  Repository: $REPO_ROOT"
echo "  Database:   $ALLBRAIN_DIR/"
echo "  Isolate:    $ISOLATE"
echo ""

# ---------------------------------------------------------------------------
# Codex  →  .codex/config.toml
# ---------------------------------------------------------------------------
if [ "$INSTALL_CODEX" = true ]; then
    echo "  [1/4] Codex …"
    mkdir -p "$REPO_ROOT/.codex"
    DB_PATH=$(resolve_db_path "codex")
    cat > "$REPO_ROOT/.codex/config.toml" << EOF
[mcp_servers.allbrain]
command = "uv"
args = [
    "run",
    "allbrain",
    "start",
    "--project",
    ".",
    "--agent",
    "codex",
    "--db-path",
    "$DB_PATH",
]
cwd = "."
startup_timeout_sec = 20
tool_timeout_sec = 120
enabled = true
required = true
EOF
    echo "    Wrote $REPO_ROOT/.codex/config.toml"
fi

# ---------------------------------------------------------------------------
# Claude Code  →  .mcp.json
# ---------------------------------------------------------------------------
if [ "$INSTALL_CLAUDE" = true ]; then
    echo "  [2/4] Claude Code …"
    DB_PATH=$(resolve_db_path "claude-code")
    cat > "$REPO_ROOT/.mcp.json" << EOF
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
        "claude-code",
        "--db-path",
        "$DB_PATH"
      ],
      "cwd": ".",
      "env": {},
      "timeout": 120000
    }
  }
}
EOF
    echo "    Wrote $REPO_ROOT/.mcp.json"
fi

# ---------------------------------------------------------------------------
# OpenCode  →  .opencode/opencode.json
# ---------------------------------------------------------------------------
if [ "$INSTALL_OPENCODE" = true ]; then
    echo "  [3/4] OpenCode …"
    mkdir -p "$REPO_ROOT/.opencode"
    DB_PATH=$(resolve_db_path "opencode")
    cat > "$REPO_ROOT/.opencode/opencode.json" << EOF
{
  "\$schema": "https://opencode.ai/config.json",
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
        "opencode",
        "--db-path",
        "$DB_PATH"
      ],
      "cwd": ".",
      "enabled": true,
      "timeout": 120000
    }
  }
}
EOF
    echo "    Wrote $REPO_ROOT/.opencode/opencode.json"
fi

# ---------------------------------------------------------------------------
# Antigravity  →  ~/.gemini/antigravity/mcp_config.json  (global, merge)
# ---------------------------------------------------------------------------
if [ "$INSTALL_ANTIGRAVITY" = true ]; then
    echo "  [4/4] Antigravity (global) …"
    DB_PATH=$(resolve_db_path "antigravity")
    # Use quoted heredoc to prevent shell expansion inside Python code.
    # REPO_ROOT and DB_PATH are passed via environment variables.
    export REPO_ROOT DB_PATH ISOLATE
    python3 << 'PYEOF'
import json, os, pathlib

agent = "antigravity"
repo_root = os.environ["REPO_ROOT"]
db_path = os.environ["DB_PATH"]
isolate = os.environ.get("ISOLATE") == "true"

config_dir = pathlib.Path.home() / ".gemini" / "antigravity"
config_dir.mkdir(parents=True, exist_ok=True)
config_path = config_dir / "mcp_config.json"

if config_path.exists():
    config = json.loads(config_path.read_text())
else:
    config = {}

config.setdefault("mcpServers", {})

args = [
    "uv", "run", "allbrain", "start",
    "--project", repo_root,
    "--agent", agent,
    "--db-path", db_path,
]

config["mcpServers"]["allbrain"] = {
    "command": "uv",
    "args": args,
    "cwd": repo_root,
    "env": {},
    "timeout": 120000,
}

config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
print(f"    Merged Antigravity config at {config_path}")
PYEOF
fi

echo ""
echo "Done — restart your MCP clients to apply the new configuration."
echo "Run without --isolate to revert to the shared database."
