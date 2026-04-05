@echo off
title HybridRAG V2 — Overnight Extraction (Dual GPU)
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM ================================================================
REM  Overnight Extraction — Dual GPU Beast Runner
REM ================================================================
REM  Runs phi4:14b extraction on Clone1 chunks using both 3090s.
REM  GPU 0 handles first half, GPU 1 handles second half.
REM  Leave running overnight — resume with --resume flag.
REM
REM  Pre-reqs:
REM    - Ollama running (ollama serve)
REM    - phi4:14b-q4_K_M pulled
REM    - V2 venv set up
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
    echo [FAIL] .venv not found. Run tools\setup_beast_2026-04-05.bat first.
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
