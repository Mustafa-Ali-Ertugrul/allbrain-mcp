param(
    [switch]$All,
    [switch]$Codex,
    [switch]$Claude,
    [switch]$ClaudeDesktop,
    [switch]$OpenCode,
    [switch]$Gemini,
    [switch]$Antigravity,
    [switch]$VSCode,
    [switch]$Cursor,
    [switch]$Windsurf,
    [switch]$Zed,
    [switch]$Kiro,
    [switch]$Isolate,
    [switch]$Verify,
    [switch]$DryRun,
    [string]$Project
)

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "Python was not found on PATH." }

$clients = @()
if ($Codex) { $clients += 'codex' }
if ($Claude) { $clients += 'claude' }
if ($ClaudeDesktop) { $clients += 'claude-desktop' }
if ($OpenCode) { $clients += 'opencode' }
if ($Gemini) { $clients += 'gemini' }
if ($Antigravity) { $clients += 'antigravity' }
if ($VSCode) { $clients += 'vscode' }
if ($Cursor) { $clients += 'cursor' }
if ($Windsurf) { $clients += 'windsurf' }
if ($Zed) { $clients += 'zed' }
if ($Kiro) { $clients += 'kiro' }

$argsList = @((Join-Path $PSScriptRoot 'install_mcp_clients.py'))
if (-not $All -and $clients.Count -gt 0) { $argsList += $clients }
if ($Isolate) { $argsList += '--isolate' }
if ($Verify) { $argsList += '--verify' }
if ($DryRun) { $argsList += '--dry-run' }
if ($Project) { $argsList += @('--project', $Project) }

& $python @argsList
exit $LASTEXITCODE
