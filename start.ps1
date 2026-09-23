# Open the existing control HUD in the logged-on desktop; default is safe/paused.
param([switch]$Resume)
$ErrorActionPreference = 'Stop'
if ((Get-Process -Id $PID).SessionId -eq 0) {
    throw 'Run start.ps1 from your logged-on Windows desktop, not the remote service session.'
}
Set-Location $PSScriptRoot
if ($Resume) {
    Write-Host 'Resume is requested through the HUD after checking live telemetry and action readiness.'
}
$python = (Get-Command python -ErrorAction Stop).Source
& $python (Join-Path $PSScriptRoot 'launcher.py')
if ($LASTEXITCODE -ne 0) { throw "Launcher exited with code $LASTEXITCODE" }
Write-Host 'Launcher returned. STOP/paused state was preserved; review the HUD before resuming.'
