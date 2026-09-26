param([switch]$AllowDirty)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$python = if (Test-Path ".venv\Scripts\python.exe") {
    Resolve-Path ".venv\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    (Get-Command python).Source
} else {
    throw "Python was not found. Run Install.ps1 -Dev first."
}

& $python -m compileall -q src tools launcher.py
if ($LASTEXITCODE) { throw "compileall failed." }

& $python -m pytest -q --tb=short -p no:cacheprovider
if ($LASTEXITCODE) { throw "pytest failed." }

& $python tools\verify_checkout.py
if ($LASTEXITCODE) { throw "clean-checkout verification failed." }

git diff --check
if ($LASTEXITCODE) { throw "git diff --check failed." }
if (-not $AllowDirty) {
    $dirty = git status --porcelain
    if ($dirty) {
        Write-Host $dirty
        throw "Working tree is dirty. Commit intended changes before release verification."
    }
}

$sha = git rev-parse HEAD
Write-Host ""
Write-Host "Repository verification passed at $sha"
