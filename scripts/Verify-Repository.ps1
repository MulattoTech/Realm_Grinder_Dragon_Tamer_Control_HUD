param([switch]$AllowDirty)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$python = $null
$pythonArgs = @()
if (Test-Path ".venv\Scripts\python.exe") {
    $python = (Resolve-Path ".venv\Scripts\python.exe").Path
    $version = & $python --version 2>&1
    $versionExitCode = $LASTEXITCODE
    if ($versionExitCode -ne 0 -or ($version -join " ") -notmatch "^Python 3\.12(?:\.|\s|$)") {
        throw "The project virtual environment must use Python 3.12; version check exited $versionExitCode ($($version -join ' ')). Run Install.ps1 -Dev after installing Python 3.12."
    }
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $version = & py -3.12 --version 2>&1
    $versionExitCode = $LASTEXITCODE
    if ($versionExitCode -eq 0 -and ($version -join " ") -match "^Python 3\.12(?:\.|\s|$)") {
        $python = "py"
        $pythonArgs = @("-3.12")
    }
}
if (-not $python -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
    $versionExitCode = $LASTEXITCODE
    if ($versionExitCode -eq 0 -and ($version -join " ").Trim() -eq "3.12") { $python = (Get-Command python).Source }
}
if (-not $python) { throw "Python 3.12 was not found or its version check failed. Run Install.ps1 -Dev after installing Python 3.12." }

& $python @pythonArgs -m compileall -q src tools launcher.py
if ($LASTEXITCODE) { throw "compileall failed." }

& $python @pythonArgs -m pytest -q --tb=short -p no:cacheprovider
if ($LASTEXITCODE) { throw "pytest failed." }

& $python @pythonArgs tools\verify_checkout.py
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
