<#
.SYNOPSIS
Prepares the complete AI handoff for Claude 3.7 / Sonnet 4.6 (Thinking),
verifies test suites, packages AI_Continuance.zip, and copies the master
prompt directly to the Windows clipboard for instant pasting.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   REALM GRINDER DRAGON TAMER - CLAUDE SONNET 4.6 HANDOFF       " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Verify tests
Write-Host "[1/4] Running repository baseline test suite..." -ForegroundColor Yellow
$testResult = python -m pytest -q --tb=short
Write-Host $testResult

# 2. Package AI Continuance
Write-Host "`n[2/4] Packaging AI_Continuance.zip..." -ForegroundColor Yellow
& "$RepoRoot\scripts\Export-Continuance.ps1"

# 3. Read Master Directive Prompt
$promptFile = Join-Path $RepoRoot "docs\PROMPT-SONNET-AUTONOMOUS-GOAL.md"
if (-not (Test-Path $promptFile)) {
    throw "Prompt file not found: $promptFile"
}

$promptContent = Get-Content -Path $promptFile -Raw -Encoding utf8

# 4. Copy to Clipboard
Write-Host "`n[3/4] Copying master directive to Windows clipboard..." -ForegroundColor Yellow
try {
    Set-Clipboard -Value $promptContent
    Write-Host "[OK] Master directive prompt copied to clipboard!" -ForegroundColor Green
} catch {
    Write-Warning "Could not copy to clipboard automatically: $_"
}

Write-Host "`n[4/4] Handoff Package Ready:" -ForegroundColor Green
Write-Host "  - Master Prompt : docs\PROMPT-SONNET-AUTONOMOUS-GOAL.md (COPIED TO CLIPBOARD)" -ForegroundColor White
Write-Host "  - Archive       : AI_Continuance.zip (contains full memory & handoff docs)" -ForegroundColor White
Write-Host "  - Target Branch : feat/air-memory-engine @ $(git rev-parse --short HEAD)" -ForegroundColor White
Write-Host "`n>>> You can now press CTRL+V directly in Claude Sonnet 4.6 to begin the sprint! <<<`n" -ForegroundColor Cyan
