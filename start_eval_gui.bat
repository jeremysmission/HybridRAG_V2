@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Starts the HybridRAG V2 Eval GUI (production 400-query eval runner).
@REM How to follow: Double-click this file, or run from a terminal to see errors.
@REM Inputs: This repo folder with .venv already created.
@REM Outputs: A running Eval GUI window or a plain-English error message.
@REM Safety notes: If startup fails, rerun from a terminal so the error text stays visible.
@REM ============================
@echo off
title HybridRAG V2 Eval GUI
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "VENV_PYTHONW=%PROJECT_ROOT%\.venv\Scripts\pythonw.exe"
set "VENV_ACTIVATE=%PROJECT_ROOT%\.venv\Scripts\activate.bat"
set "GUI_SCRIPT=%PROJECT_ROOT%\scripts\eval_gui.py"
set "GUI_MODE=terminal"
set "DRY_RUN=0"
set "PASSTHROUGH_ARGS="

:parse_args
if "%~1"=="" goto after_parse_args
if /I "%~1"=="--detach" (
  set "GUI_MODE=detached"
  shift
  goto parse_args
)
if /I "%~1"=="--terminal" (
  set "GUI_MODE=terminal"
  shift
  goto parse_args
)
if /I "%~1"=="--dry-run" (
  set "DRY_RUN=1"
  shift
  goto parse_args
)
set "PASSTHROUGH_ARGS=!PASSTHROUGH_ARGS! "%~1""
shift
goto parse_args

:after_parse_args

set "LAUNCH_EXE=%VENV_PYTHON%"
if /I "%GUI_MODE%"=="detached" set "LAUNCH_EXE=%VENV_PYTHONW%"

if not defined CUDA_VISIBLE_DEVICES set "CUDA_VISIBLE_DEVICES=0"

if "%DRY_RUN%"=="1" goto dry_run

REM --- Pre-flight checks ---
if not exist "%VENV_PYTHON%" goto missing_venv
if not exist "%GUI_SCRIPT%" goto missing_gui_script
for %%A in ("%VENV_PYTHON%") do if %%~zA EQU 0 goto broken_venv
"%VENV_PYTHON%" -c "import sys" >nul 2>nul
if errorlevel 1 goto broken_venv

REM --- Environment setup ---
set "PYTHONPATH=%PROJECT_ROOT%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "NO_PROXY=localhost,127.0.0.1"
set "no_proxy=localhost,127.0.0.1"

REM Single-CUDA-GPU workstation default. Override before launch if needed.
if not defined CUDA_VISIBLE_DEVICES set "CUDA_VISIBLE_DEVICES=0"

REM Activate venv
if exist "%VENV_ACTIVATE%" call "%VENV_ACTIVATE%" >nul 2>nul

REM --- Launch ---
if /I "%GUI_MODE%"=="detached" if exist "%VENV_PYTHONW%" set "LAUNCH_EXE=%VENV_PYTHONW%"
if /I "%GUI_MODE%"=="detached" goto launch_detached

echo [INFO] Launching HybridRAG V2 Eval GUI from "%PROJECT_ROOT%"
echo [INFO] GPU: CUDA_VISIBLE_DEVICES=%CUDA_VISIBLE_DEVICES%
"%LAUNCH_EXE%" "%GUI_SCRIPT%" !PASSTHROUGH_ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto launch_failed
goto end

:launch_detached
echo [INFO] Launching HybridRAG V2 Eval GUI (detached) from "%PROJECT_ROOT%"
start "" "%LAUNCH_EXE%" "%GUI_SCRIPT%" !PASSTHROUGH_ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto launch_failed
goto end

:dry_run
echo HybridRAG V2 Eval GUI launcher -- dry run
echo.
echo Project root:    %PROJECT_ROOT%
echo Python exe:      %VENV_PYTHON%
echo Pythonw exe:     %VENV_PYTHONW%
echo Activate script: %VENV_ACTIVATE%
echo GUI script:      %GUI_SCRIPT%
echo Launch exe:      %LAUNCH_EXE%
echo Launch mode:     %GUI_MODE%
echo CUDA devices:    %CUDA_VISIBLE_DEVICES%
echo Args:            !PASSTHROUGH_ARGS!
exit /b 0

:missing_venv
echo.
echo [FAIL] Virtual environment not found.
echo Expected Python here:
echo   "%VENV_PYTHON%"
echo.
echo Install first by running:
echo   INSTALL_EVAL_GUI.bat
echo.
call :maybe_pause
exit /b 2

:broken_venv
echo.
echo [FAIL] Found .venv but Python cannot start.
echo   "%VENV_PYTHON%"
echo.
echo Rebuild by running:
echo   INSTALL_EVAL_GUI.bat
echo.
call :maybe_pause
exit /b 4

:missing_gui_script
echo.
echo [FAIL] Eval GUI entrypoint not found.
echo Expected file:
echo   "%GUI_SCRIPT%"
echo.
echo The repo may be incomplete. Re-clone or restore scripts\eval_gui.py.
call :maybe_pause
exit /b 3

:launch_failed
echo.
echo [FAIL] Eval GUI exited with code %EXIT_CODE%.
echo.
echo If you double-clicked this file, rerun from a terminal to see the full error.
echo.
echo Common checks:
echo   - Is the LanceDB store present? (config.paths.lance_db)
echo   - Does the query pack JSON exist?
echo   - Is CUDA available? (nvidia-smi)
call :maybe_pause
exit /b %EXIT_CODE%

:maybe_pause
if /I "%HYBRIDRAG_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0

:end
endlocal
exit /b 0
