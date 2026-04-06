@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Runs the HybridRAG V2 workstation installer with PowerShell bypass enabled.
@REM How to follow: Double-click this file from Explorer, or run it from cmd.exe / PowerShell.
@REM Inputs: Repo folder with tools\setup_beast_2026-04-05.ps1 present.
@REM Outputs: .venv, installed packages, and a verified local workstation setup.
@REM ============================
@echo off
title HybridRAG V2 Workstation Install
setlocal
cd /d "%~dp0"
echo [INFO] HybridRAG V2 workstation install
echo [INFO] Repo root: %CD%
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup_beast_2026-04-05.ps1"
pause
endlocal
