@echo off
setlocal EnableDelayedExpansion
for /f "tokens=2 delims=:." %%A in ('chcp') do set "_PREV_CP=%%A"
set "_PREV_CP=%_PREV_CP: =%"
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
set "HYBRIDRAG_PROJECT_ROOT=%REPO_ROOT%"

pushd "%REPO_ROOT%" >nul

if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    "%REPO_ROOT%\.venv\Scripts\python.exe" tools\autotune\autotune_preflight.py %*
    set "EXIT_CODE=!ERRORLEVEL!"
    popd >nul
    exit /b !EXIT_CODE!
)

where py >nul 2>nul
if !ERRORLEVEL! EQU 0 (
    py -3 tools\autotune\autotune_preflight.py %*
    set "EXIT_CODE=!ERRORLEVEL!"
    popd >nul
    exit /b !EXIT_CODE!
)

where python >nul 2>nul
if !ERRORLEVEL! EQU 0 (
    python tools\autotune\autotune_preflight.py %*
    set "EXIT_CODE=!ERRORLEVEL!"
    popd >nul
    exit /b !EXIT_CODE!
)

echo [FAIL] Python was not found.
echo         Checked:
echo           %REPO_ROOT%\.venv\Scripts\python.exe
echo           py -3
echo           python
popd >nul
chcp %_PREV_CP% >nul 2>&1
exit /b 9009
