@echo off
setlocal

@REM GUI version of the walk-away import + extraction pipeline.
@REM Same proxy/cert/encoding safety as RUN_IMPORT_AND_EXTRACT.bat.
@REM
@REM Usage:  Double-click this file, or run from terminal.
@REM         The GUI will open — browse to export folder, click Start.

cd /d "%~dp0"

@REM === Workstation environment safety (proxy, certs, encoding) ===
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "NO_PROXY=127.0.0.1,localhost"
set "no_proxy=127.0.0.1,localhost"

if not exist ".venv\Scripts\pythonw.exe" (
    if not exist ".venv\Scripts\python.exe" (
        echo ERROR: HybridRAG V2 virtual environment not found at .venv\Scripts\
        echo Run the installer first.
        pause
        exit /b 2
    )
)

@REM Use pythonw.exe (no console window) if available, else fall back to python.exe
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "scripts\import_extract_gui.py"
) else (
    ".venv\Scripts\python.exe" "scripts\import_extract_gui.py"
)

endlocal
