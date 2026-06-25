param(
    [switch]$Codex,
    [switch]$Claude,
    [switch]$OpenCode,
    [switch]$Antigravity,
    [switch]$All
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

if ($Codex) {
    $codexPath = Join-Path $repoRoot '.codex\config.toml'
    Write-Text $codexPath @'
[mcp_servers.allbrain]
command = "uv"
args = ["run", "allbrain", "start", "--project", ".", "--agent", "codex"]
cwd = "."
startup_timeout_sec = 20
tool_timeout_sec = 120
enabled = true
required = true
'@
}

if ($Claude) {
    $claudePath = Join-Path $repoRoot '.mcp.json'
    Write-Text $claudePath @'
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
      "cwd": ".",
      "env": {},
      "timeout": 120000
    }
  }
}
'@
}

if ($OpenCode) {
    $openCodePath = Join-Path $repoRoot '.opencode\opencode.json'
    Write-Text $openCodePath @'
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
      "enabled": true,
      "timeout": 120000
    }
  }
}
'@
}

if ($Antigravity) {
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
    $allbrainConfig = [pscustomobject]@{
        command = 'uv'
        args = @(
            'run'
            'allbrain'
            'start'
            '--project'
            $repoRoot
            '--agent'
            'antigravity'
        )
        cwd = $repoRoot
        env = @{}
        timeout = 120000
    }
    $antigravityConfig.mcpServers | Add-Member -NotePropertyName allbrain -NotePropertyValue $allbrainConfig -Force
    Write-Text $antigravityPath ($antigravityConfig | ConvertTo-Json -Depth 20)
}
