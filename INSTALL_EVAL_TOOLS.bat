@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Installs RAGAS evaluation tools for QA Workbench and Eval GUI.
@REM How to follow: Double-click this file from Explorer. Follow the prompts.
@REM Inputs: HybridRAG V2 repo with .venv already created.
@REM Outputs: RAGAS + rapidfuzz + all dependencies installed in .venv.
@REM Args: -NoPause (skip all operator pauses for walk-away runs)
@REM ============================
@echo off
title HybridRAG V2 - Eval Tools Install
setlocal EnableExtensions
cd /d "%~dp0"

set "SCRIPT=%~dp0tools\install_eval_tools.ps1"
set "SCRIPT_ARGS=%*"

for %%A in (%*) do (
  if /I "%%~A"=="-NoPause" set "HYBRIDRAG_NO_PAUSE=1"
  if /I "%%~A"=="--no-pause" set "HYBRIDRAG_NO_PAUSE=1"
)

echo ========================================================================
echo   HybridRAG V2 -- Eval Tools Install (RAGAS + rapidfuzz)
echo ========================================================================
echo.
echo   Repo root:  %CD%
echo   Installer:  %SCRIPT%
echo.

if not exist "%SCRIPT%" (
  echo [FAIL] Install script not found:
  echo        %SCRIPT%
  if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
  exit /b 1
)

echo [INFO] Launching with session-only PowerShell execution-policy bypass.
echo.
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
  "%ProgramFiles%\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %SCRIPT_ARGS%
) else (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %SCRIPT_ARGS%
)
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
  echo [FAIL] Eval tools install exited with code %EXIT_CODE%.
) else (
  echo [OK] Eval tools install completed successfully.
)
if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
endlocal & exit /b %EXIT_CODE%
