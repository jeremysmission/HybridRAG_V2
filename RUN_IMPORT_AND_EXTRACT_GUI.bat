@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Starts the import-and-extract GUI wrapper for operator-driven runs.
@REM How to follow: Launch it, choose the source folder, and use the buttons shown in the window.
@REM Inputs: This repo and a source export location.
@REM Outputs: A running GUI for guided import and extraction.
@REM ============================
@echo off
title HybridRAG V2 Import + Extract GUI
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "PREFLIGHT_HELPER=%PROJECT_ROOT%\scripts\gui_runtime_preflight_2026-04-15.ps1"
set "PREFLIGHT_ENV_CMD=%TEMP%\hybridrag_import_gui_preflight_%RANDOM%%RANDOM%.cmd"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "VENV_PYTHONW=%PROJECT_ROOT%\.venv\Scripts\pythonw.exe"
set "GUI_SCRIPT=%PROJECT_ROOT%\scripts\import_extract_gui.py"
set "GUI_MODE=detached"
set "DRY_RUN=0"
set "DEBUG_ENV=0"

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
echo [FAIL] Unknown argument: %~1
call :maybe_pause
exit /b 2

:after_parse_args

if not exist "%VENV_PYTHON%" goto missing_venv
if not exist "%GUI_SCRIPT%" goto missing_gui_script
if not exist "%PREFLIGHT_HELPER%" goto missing_preflight_helper
for %%A in ("%VENV_PYTHON%") do if %%~zA EQU 0 goto broken_venv
"%VENV_PYTHON%" -c "import sys" >nul 2>nul
if errorlevel 1 goto broken_venv

powershell -NoProfile -ExecutionPolicy Bypass -File "%PREFLIGHT_HELPER%" -ProjectRoot "%PROJECT_ROOT%" -LauncherName "RUN_IMPORT_AND_EXTRACT_GUI.bat" -EmitCmd > "%PREFLIGHT_ENV_CMD%"
if errorlevel 1 goto preflight_failed
call "%PREFLIGHT_ENV_CMD%"
del "%PREFLIGHT_ENV_CMD%" >nul 2>nul

echo [INFO] Runtime preflight: %HYBRIDRAG_RUNTIME_PREFLIGHT% via %HYBRIDRAG_RUNTIME_PREFLIGHT_LAUNCHER%
echo [INFO] Proxy:    HTTPS_PROXY=%HTTPS_PROXY%
echo [INFO] Proxy:    HTTP_PROXY=%HTTP_PROXY%
echo [INFO] Proxy:    ALL_PROXY=%ALL_PROXY%
echo [INFO] Proxy:    NO_PROXY=%NO_PROXY%
echo [INFO] Proxy:    inherited=%HYBRIDRAG_RUNTIME_PROXY_PRESENT% cert_env=%HYBRIDRAG_RUNTIME_CERT_ENV_PRESENT%
echo [INFO] UTF-8:    PYTHONUTF8=%PYTHONUTF8% PYTHONIOENCODING=%PYTHONIOENCODING%
if "%DEBUG_ENV%"=="1" (
  echo [INFO] REQUESTS_CA_BUNDLE=%REQUESTS_CA_BUNDLE%
  echo [INFO] SSL_CERT_FILE=%SSL_CERT_FILE%
  echo [INFO] HTTPS_PROXY_CA=%HTTPS_PROXY_CA%
)

if "%DRY_RUN%"=="1" goto dry_run

if /I "%GUI_MODE%"=="detached" if exist "%VENV_PYTHONW%" goto launch_detached

echo [INFO] Launching HybridRAG V2 Import + Extract GUI in terminal mode
"%VENV_PYTHON%" "%GUI_SCRIPT%"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto launch_failed
goto end

:launch_detached
echo [INFO] Launching HybridRAG V2 Import + Extract GUI (detached)
start "" "%VENV_PYTHONW%" "%GUI_SCRIPT%"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto launch_failed
goto end

:dry_run
echo HybridRAG V2 Import/Extract GUI launcher -- dry run
echo.
echo Project root:    %PROJECT_ROOT%
echo Python exe:      %VENV_PYTHON%
echo Pythonw exe:     %VENV_PYTHONW%
echo GUI script:      %GUI_SCRIPT%
echo Launch mode:     %GUI_MODE%
echo Preflight:       %PREFLIGHT_HELPER%
echo PythonUTF8:      %PYTHONUTF8%
echo PythonIO:        %PYTHONIOENCODING%
echo HTTP_PROXY:      %HTTP_PROXY%
echo HTTPS_PROXY:     %HTTPS_PROXY%
echo ALL_PROXY:       %ALL_PROXY%
echo NO_PROXY:        %NO_PROXY%
echo Proxy present:   %HYBRIDRAG_RUNTIME_PROXY_PRESENT%
echo Cert env:        %HYBRIDRAG_RUNTIME_CERT_ENV_PRESENT%
exit /b 0

:missing_venv
echo.
echo [FAIL] Virtual environment not found.
echo Expected Python here:
echo   "%VENV_PYTHON%"
echo.
echo Run the install path first.
call :maybe_pause
exit /b 2

:broken_venv
echo.
echo [FAIL] Found .venv but Python cannot start.
echo   "%VENV_PYTHON%"
echo.
echo Rebuild the environment before launching this GUI.
call :maybe_pause
exit /b 4

:missing_gui_script
echo.
echo [FAIL] Import/Extract GUI entrypoint not found.
echo Expected file:
echo   "%GUI_SCRIPT%"
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
echo [FAIL] Import/Extract GUI exited with code %EXIT_CODE%.
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
