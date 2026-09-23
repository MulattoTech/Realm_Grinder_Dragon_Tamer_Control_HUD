# Stop only this project's automation; keep Realm Grinder itself untouched.
$ErrorActionPreference = 'Stop'
$stopFile = Join-Path $PSScriptRoot 'state\STOP'
'Paused by stop.ps1' | Set-Content -Path $stopFile -Encoding utf8
$cfgFile = Join-Path $PSScriptRoot 'state\bot_config.json'
if (Test-Path $cfgFile) {
    $cfg = Get-Content -Raw $cfgFile | ConvertFrom-Json
    $cfg | Add-Member -NotePropertyName paused -NotePropertyValue $true -Force
    $temporary = "$cfgFile.stop.tmp"
    $cfg | ConvertTo-Json -Depth 20 | Set-Content $temporary -Encoding utf8
    Move-Item $temporary $cfgFile -Force
}
$projectPattern = [regex]::Escape($PSScriptRoot)
$workers = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('python.exe','pythonw.exe') -and
    $_.CommandLine -match $projectPattern -and $_.CommandLine -match 'state_machine\.py'
}
foreach ($worker in $workers) { Stop-Process -Id $worker.ProcessId }
Write-Host 'STOP and paused=true are set. The embedded HUD worker will observe the stop; the game was not terminated.'
