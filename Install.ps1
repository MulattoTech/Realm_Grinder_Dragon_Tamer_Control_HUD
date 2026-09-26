param(
    [switch]$Dev,
    [string]$GameDir = ""
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq "Core") {
    throw "Realm Grinder Dragon Tamer currently targets Windows."
}

$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    try { & py -3.12 --version *> $null; $py = @("py","-3.12") } catch {}
}
if (-not $py -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($version -eq "3.12") { $py = @("python") }
}
if (-not $py) { throw "Python 3.12 is required." }

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if ($py.Count -eq 2) { & $py[0] $py[1] -m venv .venv } else { & $py[0] -m venv .venv }
}
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
$requirements = if ($Dev) { "requirements-dev.txt" } else { "requirements.txt" }
& $python -m pip install -r $requirements

$bootstrap = @("tools\bootstrap.py")
if ($GameDir) { $bootstrap += @("--game-dir",$GameDir) }
& $python @bootstrap
if ($LASTEXITCODE -ne 0) { throw "Bootstrap failed with exit code $LASTEXITCODE." }

Write-Host ""
Write-Host "Installation complete."
Write-Host "Launch from the logged-on Windows desktop with:"
Write-Host "  .\.venv\Scripts\python.exe launcher.py"
if ($Dev) {
    Write-Host "Verify the repository with:"
    Write-Host "  .\scripts\Verify-Repository.ps1"
}
