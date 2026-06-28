param(
    [switch]$Codex,
    [switch]$Claude,
    [switch]$OpenCode,
    [switch]$Antigravity,
    [switch]$All,
    [switch]$Isolate
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    throw "uv was not found on PATH. Install uv first, then rerun this script."
}

if ($All -or (-not $Codex -and -not $Claude -and -not $OpenCode -and -not $Antigravity)) {
    $Codex = $Claude = $OpenCode = $Antigravity = $true
}

function Ensure-Dir([string]$Path) {
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

function Write-Text([string]$Path, [string]$Text) {
    Ensure-Dir $Path
    Set-Content -LiteralPath $Path -Value $Text -Encoding utf8
    Write-Host "Wrote $Path"
}

# Resolve the database path for a given agent.
# Always returns an absolute path with forward slashes for JSON/TOML compatibility.
# Default (shared):  ~/.allbrain/allbrain.db
# --Isolate:          ~/.allbrain/<agent>.db
function Get-DbPath([string]$AgentName) {
    $homePath = $env:USERPROFILE -replace '\\', '/'
    $dbDir = "$homePath/.allbrain"
    if (-not (Test-Path $dbDir)) {
        New-Item -ItemType Directory -Path $dbDir -Force | Out-Null
    }
    if ($Isolate) {
        return "$dbDir/$AgentName.db"
    }
    return "$dbDir/allbrain.db"
}

Write-Host "AllBrain MCP — installing MCP client configurations"
Write-Host "  Repository: $repoRoot"
Write-Host "  Database:   $env:USERPROFILE\.allbrain\"
Write-Host "  Isolate:    $Isolate"
Write-Host ""

if ($Codex) {
    Write-Host "  [1/4] Codex …"
    $codexPath = Join-Path $repoRoot '.codex\config.toml'
    $dbPath = Get-DbPath "codex"
    Write-Text $codexPath @"
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
    "$dbPath",
]
cwd = "."
startup_timeout_sec = 20
tool_timeout_sec = 120
enabled = true
required = true
"@
}

if ($Claude) {
    Write-Host "  [2/4] Claude Code …"
    $claudePath = Join-Path $repoRoot '.mcp.json'
    $dbPath = Get-DbPath "claude-code"
    Write-Text $claudePath @"
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
        "$dbPath"
      ],
      "cwd": ".",
      "env": {},
      "timeout": 120000
    }
  }
}
"@
}

if ($OpenCode) {
    Write-Host "  [3/4] OpenCode …"
    $openCodePath = Join-Path $repoRoot '.opencode\opencode.json'
    $dbPath = Get-DbPath "opencode"
    Write-Text $openCodePath @"
{
  "`$schema": "https://opencode.ai/config.json",
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
        "$dbPath"
      ],
      "cwd": ".",
      "enabled": true,
      "timeout": 120000
    }
  }
}
"@
}

if ($Antigravity) {
    Write-Host "  [4/4] Antigravity (global) …"
    $antigravityPath = Join-Path $env:USERPROFILE '.gemini\antigravity\mcp_config.json'
    Ensure-Dir $antigravityPath
    if (Test-Path $antigravityPath) {
        $antigravityConfig = Get-Content -LiteralPath $antigravityPath -Raw | ConvertFrom-Json
    } else {
        $antigravityConfig = [pscustomobject]@{}
    }
    if (-not $antigravityConfig.PSObject.Properties['mcpServers']) {
        $antigravityConfig | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
    }
    # Forward slashes in JSON config values for cross-platform compatibility
    $configRepoRoot = $repoRoot -replace '\\', '/'
    $dbPath = Get-DbPath "antigravity"
    $allbrainConfig = [pscustomobject]@{
        command = 'uv'
        args = @(
            'uv'
            'run'
            'allbrain'
            'start'
            '--project'
            $configRepoRoot
            '--agent'
            'antigravity'
            '--db-path'
            $dbPath
        )
        cwd = $configRepoRoot
        env = @{}
        timeout = 120000
    }
    $antigravityConfig.mcpServers | Add-Member -NotePropertyName allbrain -NotePropertyValue $allbrainConfig -Force
    Write-Text $antigravityPath ($antigravityConfig | ConvertTo-Json -Depth 20)
}

Write-Host ""
Write-Host "Done — restart your MCP clients to apply the new configuration."
Write-Host "Run without -Isolate to revert to the shared database."
