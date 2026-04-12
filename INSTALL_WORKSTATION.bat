@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Runs the HybridRAG V2 canonical workstation installer with PowerShell bypass enabled.
@REM How to follow: Double-click this file from Explorer, or run it from cmd.exe / PowerShell.
@REM Inputs: Repo folder with tools\setup_workstation_2026-04-12.ps1 present.
@REM Outputs: .venv, installed packages, and a verified local workstation setup.
@REM Args: Pass-through to the active dated PS1, e.g. INSTALL_WORKSTATION.bat -DryRun -NoPause
@REM ============================
@echo off
title HybridRAG V2 Workstation Install
setlocal EnableExtensions
cd /d "%~dp0"
set "SCRIPT=%~dp0tools\setup_workstation_2026-04-12.ps1"
set "SCRIPT_ARGS=%*"

for %%A in (%*) do (
  if /I "%%~A"=="-NoPause" set "HYBRIDRAG_NO_PAUSE=1"
  if /I "%%~A"=="--no-pause" set "HYBRIDRAG_NO_PAUSE=1"
)

echo [INFO] HybridRAG V2 workstation install
echo [INFO] Repo root: %CD%
echo [INFO] Canonical installer: %SCRIPT%
if not exist "%SCRIPT%" (
  echo [FAIL] Installer PowerShell script not found:
  echo        %SCRIPT%
  if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
  exit /b 1
)

echo [INFO] Pass-through args: %SCRIPT_ARGS%
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
  "%ProgramFiles%\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %SCRIPT_ARGS%
) else (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %SCRIPT_ARGS%
)
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
  echo [FAIL] HybridRAG V2 workstation install exited with code %EXIT_CODE%.
) else (
  echo [OK] HybridRAG V2 workstation install finished.
)
if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
endlocal & exit /b %EXIT_CODE%
