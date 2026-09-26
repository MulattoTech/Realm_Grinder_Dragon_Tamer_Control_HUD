@echo off
setlocal enabledelayedexpansion

:: 1. Define paths relative to this script
set "REALM_DIR=%~dp0"
:: Remove trailing backslash if present
if "%REALM_DIR:~-1%"=="\" set "REALM_DIR=%REALM_DIR:~0,-1%"

set "TEMP_CODEX_HOME=%USERPROFILE%\.codex-realmgrinder"
set "GLOBAL_CODEX_CONFIG=%USERPROFILE%\.codex\config.toml"

echo [=] Launching isolated Codex session...
echo [=] Working Directory: %REALM_DIR%

:: 2. Ensure the isolated configuration home directory exists
if not exist "%TEMP_CODEX_HOME%" (
    mkdir "%TEMP_CODEX_HOME%"
    echo [+] Created isolated configuration folder.
)

:: 3. Sync the global config file if it exists, without locking it
if exist "%GLOBAL_CODEX_CONFIG%" (
    copy /Y "%GLOBAL_CODEX_CONFIG%" "%TEMP_CODEX_HOME%\config.toml" >nul
    echo [+] Configuration synced from global profile.
)

:: 4. Set environment and pivot
cd /d "%REALM_DIR%"
set "CODEX_HOME=%TEMP_CODEX_HOME%"

:: 5. Execute Codex CLI
echo [=] Starting Codex CLI session...
codex
pause
