# Launch Realm Grinder Dragon Tamer HUD Window
$script = Join-Path $PSScriptRoot "src\monitor_window.py"
Start-Process "pythonw.exe" -ArgumentList "`"$script`"" -WorkingDirectory $PSScriptRoot
Write-Host "Dragon Tamer Monitor HUD window launched on desktop." -ForegroundColor Cyan
