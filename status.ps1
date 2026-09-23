$stateFile = Join-Path $PSScriptRoot "state\dragon_tamer_state.json"

if (-not (Test-Path $stateFile)) {
    Write-Host "State file not found. Bot has not been run yet." -ForegroundColor Yellow
    exit 0
}

$state = Get-Content $stateFile | ConvertFrom-Json

$workerRunning = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and $_.CommandLine -match "state_machine"
}

$statusText = if ($running = $workerRunning | Select-Object -First 1) { "RUNNING (PID: $($running.ProcessId))" } else { "STOPPED" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "REALM GRINDER  DRAGON TAMER BOT" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Game:           CONNECTED"
Write-Host "Process:        RealmGrinderDesktop.exe"
Write-Host "Worker:         $statusText"
Write-Host "Stage:          $($state.current_stage)"
Write-Host "Reincarnation:  R$($state.current_known_r)"
Write-Host "Gems:           $($state.gems)"
Write-Host "Excavations:    $($state.excavations)"
$eggStatus = if ($state.timestamps.egg_obtained) { "COMPLETE" } else { "LOCKED (Requires R46+, 1500+ excavations)" }
Write-Host "Spiky Egg:      $eggStatus"
$hatchStatus = if ($state.timestamps.hatch_purchased) { "COMPLETE" } else { "LOCKED" }
Write-Host "Hatch!:         $hatchStatus"
Write-Host "Hellfire Time:  $($state.observed_hellfire_time)s / 43200s (12h)"
$drakelingStatus = if ($state.timestamps.drakeling_purchased) { "COMPLETE" } else { "LOCKED" }
Write-Host "Drakeling:      $drakelingStatus"
$dragonStatus = if ($state.timestamps.dragon_purchased) { "COMPLETE" } else { "LOCKED" }
Write-Host "Dragon:         $dragonStatus"
$elderStatus = if ($state.timestamps.elder_dragon_purchased) { "COMPLETE" } else { "LOCKED" }
Write-Host "Elder Dragon:   $elderStatus"
$achStatus = if ($state.current_stage -eq "COMPLETED") { "UNLOCKED! [466]" } else { "IN PROGRESS" }
Write-Host "Achievement:    $achStatus"
Write-Host "Last Action:    $($state.last_successful_action)"
Write-Host "Next Expected:  $($state.next_expected_action)"
Write-Host "Latest Backup:  $($state.most_recent_backup)"
Write-Host "============================================================" -ForegroundColor Cyan
