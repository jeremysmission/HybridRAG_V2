@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Delegates to the dated workstation setup flow for this repo.
@REM How to follow: Use it as the launcher entrypoint if you want the pinned setup version.
@REM Inputs: This repo checkout.
@REM Outputs: The dated workstation setup process for HybridRAG V2.
@REM ============================
@echo off
title HybridRAG V2 Workstation Setup
setlocal EnableExtensions
cd /d "%~dp0"

set "SCRIPT=%~dp0setup_workstation_2026-04-12.ps1"
set "SCRIPT_ARGS=%*"

for %%A in (%*) do (
  if /I "%%~A"=="-NoPause" set "HYBRIDRAG_NO_PAUSE=1"
  if /I "%%~A"=="--no-pause" set "HYBRIDRAG_NO_PAUSE=1"
)

if not exist "%SCRIPT%" (
  echo [FAIL] Setup script not found:
  echo        %SCRIPT%
  if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
  exit /b 1
)

echo [INFO] HybridRAG V2 workstation setup
echo [INFO] Active script: %SCRIPT%
echo [INFO] Pass-through args: %SCRIPT_ARGS%
echo [INFO] Launching with session-only PowerShell execution-policy bypass.
echo [INFO] The installer will assess the workstation first and pause at
echo [INFO] meaningful checkpoints inside the PowerShell stage itself.
echo [INFO] Set HYBRIDRAG_NO_PAUSE=1 to bypass all pauses for walk-away runs.
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
  "%ProgramFiles%\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %SCRIPT_ARGS%
) else (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %SCRIPT_ARGS%
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
