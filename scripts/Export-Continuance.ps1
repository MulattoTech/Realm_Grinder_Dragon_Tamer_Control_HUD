param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Creating AI Continuance Package..." -ForegroundColor Cyan

# 1. Determine commit and branch
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
$sha = (git rev-parse HEAD).Trim()
$short = (git rev-parse --short=10 HEAD).Trim()
$timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")

if (-not $OutputPath) {
    $dist = Join-Path $Root "dist"
    New-Item -ItemType Directory -Force -Path $dist | Out-Null
    $OutputPath = Join-Path $dist "AI_Continuance-$timestamp-$short.zip"
}

# 2. Prepare staging directory
$stageDir = Join-Path ([System.IO.Path]::GetTempPath()) "AI_Continuance_$timestamp"
if (Test-Path $stageDir) { Remove-Item -Recurse -Force $stageDir }
New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

try {
    # Copy essential guidance docs
    $docsToCopy = @(
        "README.md",
        "AGENTS.md",
        "docs/AI-CONTINUANCE.md",
        "docs/CURRENT-HANDOFF.md",
        "docs/CLAUDE-HANDOFF.md",
        "docs/PROMPT-SONNET-MEMORY-ENGINE.md"
    )

    foreach ($file in $docsToCopy) {
        $sourcePath = Join-Path $Root $file
        if (Test-Path $sourcePath) {
            $destPath = Join-Path $stageDir $file
            $destParent = Split-Path -Parent $destPath
            if (-not (Test-Path $destParent)) { New-Item -ItemType Directory -Force -Path $destParent | Out-Null }
            Copy-Item $sourcePath $destPath -Force
        }
    }

    # Generate Git status & uncommitted diff
    git status > (Join-Path $stageDir "git_status.txt")
    git log -15 --oneline --decorate --graph > (Join-Path $stageDir "git_log.txt")
    
    $diff = git diff HEAD
    if ($diff) {
        $diff | Set-Content -Encoding utf8 (Join-Path $stageDir "git_uncommitted.patch")
        Write-Host "Captured uncommitted working tree diff into git_uncommitted.patch" -ForegroundColor Yellow
    }

    # Create standalone Git bundle (portable repository history up to HEAD)
    $bundlePath = Join-Path $stageDir "continuance.bundle"
    git bundle create $bundlePath HEAD
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Created self-contained git bundle: continuance.bundle" -ForegroundColor Green
    }

    # Create root RESUME_INSTRUCTIONS.md
    $instructions = @"
# AI Continuance Package - Resumption Guide

Welcome. This package was generated to enable seamless handover to any AI agent (Claude, Gemini, GPT, DeepSeek, etc.).

## Repository Snapshot
- **Branch**: $branch
- **Commit HEAD**: $sha ($short)
- **Timestamp**: $timestamp
- **GitHub Origin**: https://github.com/MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD.git

## Quick Start for Resuming Agent
1. **Clone or Extract**:
   - If setting up a fresh workspace, clone the GitHub repository:
     `git clone https://github.com/MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD.git`
   - Or restore directly from the bundled git history:
     `git clone continuance.bundle Realm_Grinder`
2. **Apply Uncommitted Changes (if any)**:
   - If `git_uncommitted.patch` exists and is non-empty, apply it:
     `git apply git_uncommitted.patch`
3. **Environment Setup**:
   - Run in PowerShell:
     `py -3.12 -m venv .venv`
     `.\.venv\Scripts\Activate.ps1`
     `python -m pip install -r requirements-dev.txt`
     `python tools/bootstrap.py`
4. **Current Status & Goals**:
   - Read `docs/AI-CONTINUANCE.md` and `docs/CURRENT-HANDOFF.md`.
   - Read `docs/PROMPT-SONNET-MEMORY-ENGINE.md` for technical AVM2 details.
   - Run tests: `python -m pytest -q --tb=short`
5. **Safety Constraints**:
   - Read-only game memory only (`PROCESS_VM_READ | PROCESS_QUERY_INFORMATION`).
   - Zero save editing, zero DLL injection, zero Steam achievement API calls.
"@

    $instructions | Set-Content -Encoding utf8 (Join-Path $stageDir "RESUME_INSTRUCTIONS.md")

    # Zip everything
    if (Test-Path $OutputPath) { Remove-Item $OutputPath -Force }
    Compress-Archive -Path "$stageDir\*" -DestinationPath $OutputPath -Force
    
    # Also place a copy at the repository root as 'AI_Continuance.zip' for instant accessibility
    $rootZip = Join-Path $Root "AI_Continuance.zip"
    Copy-Item $OutputPath $rootZip -Force

    Write-Host "Successfully exported AI Continuance package to:" -ForegroundColor Green
    Write-Host " - $OutputPath" -ForegroundColor White
    Write-Host " - $rootZip" -ForegroundColor White
}
finally {
    if (Test-Path $stageDir) {
        Remove-Item -Recurse -Force $stageDir -ErrorAction SilentlyContinue
    }
}
