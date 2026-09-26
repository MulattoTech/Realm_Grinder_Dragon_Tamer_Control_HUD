<#
.SYNOPSIS
Packages the repository handoff state, test records, memory probe telemetry, and git context into AI_Continuance.zip.
#>
[CmdletBinding()]
param(
    [string]$OutputFile = "AI_Continuance.zip"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "Exporting AI Continuance package from $RepoRoot..." -ForegroundColor Cyan
python "$RepoRoot\tools\export_continuance.py"

if (Test-Path "$RepoRoot\$OutputFile") {
    $item = Get-Item "$RepoRoot\$OutputFile"
    Write-Host "[OK] Created $OutputFile ($([math]::Round($item.Length / 1KB, 1)) KB)" -ForegroundColor Green
} else {
    throw "Failed to create $OutputFile"
}
