@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Starts the QA workbench shell that groups several quality surfaces together.
@REM How to follow: Use it when you want the management-facing QA dashboard.
@REM Inputs: This repo with the required local environment.
@REM Outputs: The QA workbench window.
@REM ============================
@echo off
title HybridRAG V2 QA Workbench
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "PREFLIGHT_HELPER=%PROJECT_ROOT%\scripts\gui_runtime_preflight_2026-04-15.ps1"
set "PREFLIGHT_ENV_CMD=%TEMP%\hybridrag_qa_workbench_preflight_%RANDOM%%RANDOM%.cmd"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "VENV_PYTHONW=%PROJECT_ROOT%\.venv\Scripts\pythonw.exe"
set "VENV_ACTIVATE=%PROJECT_ROOT%\.venv\Scripts\activate.bat"
set "GUI_SCRIPT=%PROJECT_ROOT%\src\gui\qa_workbench.py"
set "GUI_MODULE=src.gui.qa_workbench"
set "GUI_MODE=terminal"
set "DRY_RUN=0"
set "DEBUG_ENV=0"
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
if /I "%~1"=="--debug-env" (
  set "DEBUG_ENV=1"
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

if not exist "%VENV_PYTHON%" goto missing_venv
if not exist "%GUI_SCRIPT%" goto missing_gui_script
if not exist "%PREFLIGHT_HELPER%" goto missing_preflight_helper
for %%A in ("%VENV_PYTHON%") do if %%~zA EQU 0 goto broken_venv
"%VENV_PYTHON%" -c "import sys" >nul 2>nul
if errorlevel 1 goto broken_venv

REM --- Shared runtime preflight ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%PREFLIGHT_HELPER%" -ProjectRoot "%PROJECT_ROOT%" -LauncherName "start_qa_workbench.bat" -EmitCmd > "%PREFLIGHT_ENV_CMD%"
if errorlevel 1 goto preflight_failed
call "%PREFLIGHT_ENV_CMD%"
del "%PREFLIGHT_ENV_CMD%" >nul 2>nul

set "PYTHONPATH=%PROJECT_ROOT%"
set "HYBRIDRAG_NETWORK_KILL_SWITCH=0"
set "HYBRIDRAG_OFFLINE=0"

echo [INFO] Runtime preflight: %HYBRIDRAG_RUNTIME_PREFLIGHT% via %HYBRIDRAG_RUNTIME_PREFLIGHT_LAUNCHER%
echo [INFO] Proxy:    HTTPS_PROXY=%HTTPS_PROXY%
echo [INFO] Proxy:    HTTP_PROXY=%HTTP_PROXY%
echo [INFO] Proxy:    ALL_PROXY=%ALL_PROXY%
echo [INFO] Proxy:    NO_PROXY=%NO_PROXY%
echo [INFO] Proxy:    inherited=%HYBRIDRAG_RUNTIME_PROXY_PRESENT% cert_env=%HYBRIDRAG_RUNTIME_CERT_ENV_PRESENT%
echo [INFO] UTF-8:    PYTHONUTF8=%PYTHONUTF8% PYTHONIOENCODING=%PYTHONIOENCODING%
if "%DEBUG_ENV%"=="1" goto debug_env
if "%DRY_RUN%"=="1" goto dry_run

if exist "%VENV_ACTIVATE%" call "%VENV_ACTIVATE%" >nul 2>nul

if /I "%GUI_MODE%"=="detached" if exist "%VENV_PYTHONW%" set "LAUNCH_EXE=%VENV_PYTHONW%"
if /I "%GUI_MODE%"=="detached" goto launch_detached

echo [INFO] Launching HybridRAG V2 QA Workbench from "%PROJECT_ROOT%"
echo [INFO] GPU: CUDA_VISIBLE_DEVICES=%CUDA_VISIBLE_DEVICES%
echo [INFO] Python: %LAUNCH_EXE%
echo [INFO] Module: %GUI_MODULE%
"%LAUNCH_EXE%" -m %GUI_MODULE% !PASSTHROUGH_ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto launch_failed
goto end

:launch_detached
echo [INFO] Launching HybridRAG V2 QA Workbench (detached) from "%PROJECT_ROOT%"
start "" "%LAUNCH_EXE%" -m %GUI_MODULE% !PASSTHROUGH_ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto launch_failed
goto end

:dry_run
echo HybridRAG V2 QA Workbench launcher -- dry run
echo.
echo Project root:    %PROJECT_ROOT%
echo Python exe:      %VENV_PYTHON%
echo Pythonw exe:     %VENV_PYTHONW%
echo Activate script: %VENV_ACTIVATE%
echo GUI module:      %GUI_MODULE%
echo GUI script:      %GUI_SCRIPT%
echo Launch exe:      %LAUNCH_EXE%
echo Launch mode:     %GUI_MODE%
echo CUDA devices:    %CUDA_VISIBLE_DEVICES%
echo Preflight:       %PREFLIGHT_HELPER%
echo Proxy present:   %HYBRIDRAG_RUNTIME_PROXY_PRESENT%
echo Cert env:        %HYBRIDRAG_RUNTIME_CERT_ENV_PRESENT%
echo HTTP_PROXY:      %HTTP_PROXY%
echo HTTPS_PROXY:     %HTTPS_PROXY%
echo ALL_PROXY:       %ALL_PROXY%
echo NO_PROXY:        %NO_PROXY%
echo Args:            !PASSTHROUGH_ARGS!
exit /b 0

:debug_env
echo [INFO] Debug env requested before launch.
echo [INFO] REQUESTS_CA_BUNDLE=%REQUESTS_CA_BUNDLE%
echo [INFO] SSL_CERT_FILE=%SSL_CERT_FILE%
echo [INFO] HTTPS_PROXY_CA=%HTTPS_PROXY_CA%
if "%DRY_RUN%"=="1" goto dry_run

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
echo [FAIL] QA Workbench entrypoint not found.
echo Expected file:
echo   "%GUI_SCRIPT%"
echo.
echo The repo may be incomplete. Re-clone or restore src\gui\qa_workbench.py.
call :maybe_pause
exit /b 3

:missing_preflight_helper
echo.
echo [FAIL] Shared GUI runtime preflight helper not found.
echo Expected file:
echo   "%PREFLIGHT_HELPER%"
call :maybe_pause
exit /b 5

:preflight_failed
echo.
echo [FAIL] Shared GUI runtime preflight failed.
echo Helper:
echo   "%PREFLIGHT_HELPER%"
echo.
echo Check PowerShell availability and proxy/cert environment state.
call :maybe_pause
exit /b 6

:launch_failed
echo.
echo [FAIL] QA Workbench exited with code %EXIT_CODE%.
echo.
echo If you double-clicked this file, rerun from a terminal to see the full error.
echo.
echo Proxy / network debug:
echo   - HTTPS_PROXY=%HTTPS_PROXY%
echo   - HTTP_PROXY=%HTTP_PROXY%
echo   - ALL_PROXY=%ALL_PROXY%
echo   - NO_PROXY=%NO_PROXY%
echo   - inherited proxy=%HYBRIDRAG_RUNTIME_PROXY_PRESENT%
echo   - cert env=%HYBRIDRAG_RUNTIME_CERT_ENV_PRESENT%
call :maybe_pause
exit /b %EXIT_CODE%

:maybe_pause
if /I "%HYBRIDRAG_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0

:end
endlocal
exit /b 0
