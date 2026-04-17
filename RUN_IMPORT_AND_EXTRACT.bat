@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Runs the import plus extraction workflow in one walk-away step.
@REM How to follow: Point it at an export folder and then follow the printed progress lines.
@REM Inputs: A source export directory or the --skip-import flag.
@REM Outputs: Imported chunks plus extracted entities and relationships.
@REM ============================
@echo off
setlocal

@REM Walk-away script: Import CorpusForge export + Tier 1+2 extraction.
@REM Plug in E: drive, run this, walk away. Come back to a populated entity store.
@REM
@REM Usage:
@REM   RUN_IMPORT_AND_EXTRACT.bat E:\CorpusIndexEmbeddingsOnly\export_20260411_0720
@REM   RUN_IMPORT_AND_EXTRACT.bat C:\HybridRAG_V2\data\forge_exports
@REM   RUN_IMPORT_AND_EXTRACT.bat --skip-import

cd /d "%~dp0"

@REM === Workstation environment safety (proxy, certs, encoding) ===
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "NO_PROXY=127.0.0.1,localhost"
set "no_proxy=127.0.0.1,localhost"
if not defined HF_HUB_OFFLINE set "HF_HUB_OFFLINE=1"
if not defined TRANSFORMERS_OFFLINE set "TRANSFORMERS_OFFLINE=1"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: HybridRAG V2 virtual environment not found at .venv\Scripts\python.exe
    echo Run the installer first.
    pause
    exit /b 2
)

if "%~1"=="" (
    echo Usage: RUN_IMPORT_AND_EXTRACT.bat ^<source_export_dir^> [--tier 1] [--skip-import]
    echo.
    echo Example:
    echo   RUN_IMPORT_AND_EXTRACT.bat E:\CorpusIndexEmbeddingsOnly\export_20260411_0720
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   HybridRAG V2 — Walk-Away Import + Extraction
echo ============================================================
echo   Source: %1
echo   Started: %date% %time%
echo   HF offline: %HF_HUB_OFFLINE% / Transformers: %TRANSFORMERS_OFFLINE%
echo ============================================================
echo.

".venv\Scripts\python.exe" "scripts\run_full_import_and_extract.py" --source %*

set EXIT_CODE=%ERRORLEVEL%

echo.
echo ============================================================
echo   Finished: %date% %time%
echo   Exit code: %EXIT_CODE%
echo ============================================================

if /i not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
endlocal & exit /b %EXIT_CODE%
