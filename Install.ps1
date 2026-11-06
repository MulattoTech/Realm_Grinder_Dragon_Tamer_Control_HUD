param(
    [switch]$Dev,
    [string]$GameDir = ""
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq "Core") {
    throw "Realm Grinder Dragon Tamer currently targets Windows."
}

$pythonLauncher = $null
$pythonDiscoveryErrors = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $version = & py -3.12 --version 2>&1
    $versionExitCode = $LASTEXITCODE
    if ($versionExitCode -eq 0 -and ($version -join " ") -match "^Python 3\.12(?:\.|\s|$)") {
        $pythonLauncher = @("py", "-3.12")
    } else {
        $pythonDiscoveryErrors += "py -3.12 --version exited $versionExitCode ($($version -join ' '))."
    }
}
if (-not $pythonLauncher -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
    $versionExitCode = $LASTEXITCODE
    if ($versionExitCode -eq 0 -and ($version -join " ").Trim() -eq "3.12") {
        $pythonLauncher = @("python")
    } else {
        $pythonDiscoveryErrors += "python version discovery exited $versionExitCode ($($version -join ' '))."
    }
}
if (-not $pythonLauncher) {
    $details = if ($pythonDiscoveryErrors.Count) { " " + ($pythonDiscoveryErrors -join " ") } else { "" }
    throw "Python 3.12 is required.$details"
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pythonLauncher[0] @($pythonLauncher | Select-Object -Skip 1) -m venv .venv
    $venvExitCode = $LASTEXITCODE
    if ($venvExitCode -ne 0) { throw "Virtual environment creation failed with exit code $venvExitCode." }
}
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Virtual environment creation failed: .venv\Scripts\python.exe was not created." }
$installedVersion = & $python --version 2>&1
$installedVersionExitCode = $LASTEXITCODE
if ($installedVersionExitCode -ne 0 -or ($installedVersion -join " ") -notmatch "^Python 3\.12(?:\.|\s|$)") {
    throw "Virtual environment validation failed: expected Python 3.12; command exited $installedVersionExitCode ($($installedVersion -join ' '))."
}

& $python -m pip install --upgrade pip
$pipUpgradeExitCode = $LASTEXITCODE
if ($pipUpgradeExitCode -ne 0) { throw "pip upgrade failed with exit code $pipUpgradeExitCode." }
$requirements = if ($Dev) { "requirements-dev.txt" } else { "requirements.txt" }
& $python -m pip install -r $requirements
$requirementsExitCode = $LASTEXITCODE
if ($requirementsExitCode -ne 0) { throw "Dependency installation from $requirements failed with exit code $requirementsExitCode." }

$bootstrap = @("tools\bootstrap.py")
if ($GameDir) { $bootstrap += @("--game-dir",$GameDir) }
& $python @bootstrap
$bootstrapExitCode = $LASTEXITCODE
if ($bootstrapExitCode -ne 0) { throw "Bootstrap failed with exit code $bootstrapExitCode." }

Write-Host ""
Write-Host "Installation complete."
Write-Host "Launch from the logged-on Windows desktop with:"
Write-Host "  .\.venv\Scripts\python.exe launcher.py"
if ($Dev) {
    Write-Host "Verify the repository with:"
    Write-Host "  .\scripts\Verify-Repository.ps1"
}
