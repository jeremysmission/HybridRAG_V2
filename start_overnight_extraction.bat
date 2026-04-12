@echo off
title HybridRAG V2 - Clone1 / phi4 Overnight Extraction
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM ================================================================
REM  Clone1 / phi4 Overnight Extraction  -- NOT V2 tiered_extract
REM ================================================================
REM  READ THIS FIRST:
REM    This launcher runs the Clone1 / Ollama-phi4 overnight pipeline.
REM    It reads chunks from a HybridRAG3_Clone1 SQLite index (default:
REM    %USERPROFILE%\HybridRAG3_Clone1\data\index\hybridrag.sqlite3)
REM    and runs phi4:14b extraction via a local Ollama server.
REM
REM    This is NOT the V2 LanceStore Tier 1 + Tier 2 (GLiNER) pipeline.
REM    If you want V2 tiered extraction, do one of these instead:
REM
REM      .venv\Scripts\python.exe scripts\tiered_extract.py --tier 1
REM      .venv\Scripts\python.exe scripts\tiered_extract.py --tier 2
REM      start_gui.bat  (then Skip Import -> Max Tier 1/2)
REM
REM    Tier 1 (regex) is safe unattended. Tier 2 (GLiNER/GPU) has a
REM    known open issue -- do not walk away from an unbounded Tier 2
REM    run until that is fixed.
REM
REM  Pre-reqs for THIS pipeline (Clone1 / phi4):
REM    - Ollama running (ollama serve)
REM    - phi4:14b-q4_K_M pulled
REM    - V2 venv set up (see INSTALL_WORKSTATION.bat)
REM    - A populated Clone1 SQLite index reachable from this machine
REM
REM  Usage:
REM    start_overnight_extraction.bat           (default 2000 chunks)
REM    start_overnight_extraction.bat 5000      (custom limit)
REM    start_overnight_extraction.bat resume    (skip already done)
REM    start_overnight_extraction.bat status    (check progress)
REM ================================================================

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "SCRIPT=%CD%\scripts\overnight_extraction.py"
set "LIMIT=2000"
set "RESUME="

if not exist "%VENV_PYTHON%" (
    echo [FAIL] .venv not found. Run tools\setup_workstation_2026-04-06.bat first.
    pause
    exit /b 1
)

REM Parse args
if /I "%~1"=="status" (
    "%VENV_PYTHON%" "%SCRIPT%" --status
    pause
    exit /b 0
)
if /I "%~1"=="resume" (
    set "RESUME=--resume"
    if not "%~2"=="" set "LIMIT=%~2"
) else (
    if not "%~1"=="" set "LIMIT=%~1"
)

echo ================================================================
echo  HybridRAG V2 — Overnight Extraction
echo  Chunks per GPU: %LIMIT%
echo  Resume mode: %RESUME%
echo  Press Ctrl+C to stop (progress is saved)
echo ================================================================
echo.

REM Single GPU mode (simpler, default)
echo [INFO] Starting extraction on GPU 0 — %LIMIT% chunks
echo [INFO] Progress saves every 10 chunks. Safe to Ctrl+C.
echo.

set "CUDA_VISIBLE_DEVICES=0"
set "PYTHONUTF8=1"
set "PYTHONPATH=%CD%"

"%VENV_PYTHON%" "%SCRIPT%" --limit %LIMIT% --gpu 0 %RESUME%

echo.
echo [INFO] Extraction finished. Check progress:
echo   %VENV_PYTHON% %SCRIPT% --status
pause
exit /b 0
