@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Installs the HybridRAG V2 Eval GUI dependencies (same venv as main V2).
@REM How to follow: Double-click this file from Explorer, or run from cmd.exe.
@REM Inputs: Repo folder. If .venv is missing, delegates to INSTALL_WORKSTATION.bat.
@REM Outputs: Verified .venv with all eval-GUI imports resolving.
@REM ============================
@echo off
title HybridRAG V2 Eval GUI Install
setlocal EnableExtensions
cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "MAIN_INSTALLER=%PROJECT_ROOT%\INSTALL_WORKSTATION.bat"

echo [INFO] HybridRAG V2 Eval GUI install
echo [INFO] Repo root: %PROJECT_ROOT%

if not exist "%VENV_PYTHON%" (
  echo [INFO] .venv not found -- delegating to INSTALL_WORKSTATION.bat
  if not exist "%MAIN_INSTALLER%" (
    echo [FAIL] INSTALL_WORKSTATION.bat not found. Cannot bootstrap venv.
    echo        Run the HybridRAG V2 workstation installer manually first.
    if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
    exit /b 1
  )
  call "%MAIN_INSTALLER%" --no-pause
  if errorlevel 1 (
    echo [FAIL] Workstation installer failed. See messages above.
    if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
    exit /b 2
  )
)

if not exist "%VENV_PYTHON%" (
  echo [FAIL] .venv still missing after install attempt.
  if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
  exit /b 3
)

echo [INFO] Verifying eval GUI imports ...
set "PYTHONPATH=%PROJECT_ROOT%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

"%VENV_PYTHON%" -c "from src.gui.eval_panels.runner import EvalRunner; from src.gui.eval_panels.launch_panel import LaunchPanel; from src.gui.eval_panels.results_panel import ResultsPanel; from src.gui.eval_panels.compare_panel import ComparePanel; from src.gui.eval_panels.history_panel import HistoryPanel; print('eval GUI imports OK')"
set "VERIFY_EXIT=%ERRORLEVEL%"

if not "%VERIFY_EXIT%"=="0" (
  echo.
  echo [FAIL] Eval GUI import check failed. See traceback above.
  if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
  exit /b %VERIFY_EXIT%
)

echo.
echo [OK] HybridRAG V2 Eval GUI install verified.
echo     Launch with: start_eval_gui.bat
echo.
if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
endlocal & exit /b 0
