@echo off
title HybridRAG V2 Workstation Setup
setlocal EnableExtensions
cd /d "%~dp0"

set "SCRIPT=%~dp0setup_workstation_2026-04-06.ps1"

if not exist "%SCRIPT%" (
  echo [FAIL] Setup script not found:
  echo        %SCRIPT%
  pause
  exit /b 1
)

echo [INFO] HybridRAG V2 workstation setup
echo [INFO] Script: %SCRIPT%
echo [INFO] Launching with session-only PowerShell execution-policy bypass.
echo [INFO] The installer will assess the workstation first and pause at
echo [INFO] meaningful checkpoints inside the PowerShell stage itself.
echo [INFO] Set HYBRIDRAG_NO_PAUSE=1 to bypass all pauses for walk-away runs.
REM No pre-launch pause here -- the PS1 handles its own pauses at meaningful
REM decision points (post-inventory, pre-install, final summary) so operators
REM do not get stuck behind a "press any key" before the installer can even
REM tell them what it is going to do. This closes the CoPilot+ QA Medium flagged
REM on commit 0987126 about the wrapper's pop-and-wait pattern breaking the
REM "double-click and walk away" success criterion.
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
  "%ProgramFiles%\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
) else (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
)
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
  echo [FAIL] Setup exited with code %EXIT_CODE%.
) else (
  echo [OK] Setup completed.
)
if /i not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
endlocal & exit /b %EXIT_CODE%
