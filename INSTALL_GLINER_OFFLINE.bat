@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Install gliner 0.2.26 + urchade/gliner_medium-v2.1 model from a fully
@REM          offline bundle, for proxy-hardened workstations where even the
@REM          --trusted-host fallback still connection-errors on pypi fetches.
@REM
@REM Prereq: Copy vendor\gliner_offline.zip into C:\HybridRAG_V2\vendor\ first.
@REM         The zip is produced on a builder machine (e.g. Beast) by:
@REM             .\tools\build_gliner_offline_bundle.ps1
@REM
@REM Skip pause: set HYBRIDRAG_NO_PAUSE=1 for unattended runs.
@REM ============================
@echo off
title HybridRAG V2 Offline Gliner Install
setlocal EnableExtensions EnableDelayedExpansion
for /f "tokens=2 delims=:." %%A in ('chcp') do set "_PREV_CP=%%A"
set "_PREV_CP=%_PREV_CP: =%"
chcp 65001 >nul 2>&1

cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"
set "PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "BUNDLE_ZIP=%PROJECT_ROOT%\vendor\gliner_offline.zip"
set "BUNDLE_DIR=%PROJECT_ROOT%\vendor\gliner_offline"
set "WHEEL_DIR=%BUNDLE_DIR%\wheels"
set "HF_HOME=%BUNDLE_DIR%\hf_home"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "NO_PROXY=127.0.0.1,localhost"
set "no_proxy=127.0.0.1,localhost"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

if not exist "%PYTHON%" (
  echo [FAIL] Repo-local Python not found: %PYTHON%
  echo        Run INSTALL_WORKSTATION.bat first to create the venv.
  set "_EXITCODE=2"
  goto :cleanup
)

if not exist "%BUNDLE_ZIP%" (
  if not exist "%BUNDLE_DIR%\manifest.json" (
    echo [FAIL] gliner offline bundle not found.
    echo        Expected zip: %BUNDLE_ZIP%
    echo        Or unpacked:  %BUNDLE_DIR%\manifest.json
    echo.
    echo        Build on a machine with internet:
    echo            cd C:\HybridRAG_V2
    echo            .\tools\build_gliner_offline_bundle.ps1
    echo        Then copy vendor\gliner_offline.zip to this workstation.
    set "_EXITCODE=2"
    goto :cleanup
  )
)

if exist "%BUNDLE_ZIP%" (
  if not exist "%BUNDLE_DIR%\manifest.json" (
    echo [1/4] Unpacking bundle: %BUNDLE_ZIP%
    powershell -NoProfile -Command "Expand-Archive -Path '%BUNDLE_ZIP%' -DestinationPath '%BUNDLE_DIR%' -Force"
    if errorlevel 1 (
      echo [FAIL] Expand-Archive failed.
      set "_EXITCODE=3"
      goto :cleanup
    )
  ) else (
    echo [1/4] Bundle already unpacked at %BUNDLE_DIR%
  )
)

if not exist "%WHEEL_DIR%" (
  echo [FAIL] Wheels directory missing after unpack: %WHEEL_DIR%
  set "_EXITCODE=3"
  goto :cleanup
)

echo [2a/4] Installing gliner dep layer (no torch, preserves existing CUDA torch)
"%PYTHON%" -m pip install --no-index --find-links "%WHEEL_DIR%" huggingface_hub onnxruntime sentencepiece tqdm "transformers>=4.51.3,<5.2.0"
if errorlevel 1 (
  echo [FAIL] Offline dep layer install failed. Check %WHEEL_DIR% for missing transitive wheels.
  set "_EXITCODE=4"
  goto :cleanup
)

echo [2b/4] Installing --no-deps gliner==0.2.26
"%PYTHON%" -m pip install --no-index --find-links "%WHEEL_DIR%" --no-deps gliner==0.2.26
if errorlevel 1 (
  echo [FAIL] Offline gliner install failed.
  set "_EXITCODE=4"
  goto :cleanup
)

"%PYTHON%" -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
if errorlevel 1 (
  echo [FAIL] torch import failed after gliner install. Torch may have been stomped.
  set "_EXITCODE=4"
  goto :cleanup
)

echo [3/4] Verifying gliner import and model load
"%PYTHON%" -c "import gliner, os; print('gliner', gliner.__version__); print('HF_HOME', os.environ.get('HF_HOME'))"
if errorlevel 1 (
  echo [FAIL] gliner import failed after install.
  set "_EXITCODE=5"
  goto :cleanup
)

echo [4/4] Running repo verify_install.py
"%PYTHON%" "scripts\verify_install.py"
set "_EXITCODE=%ERRORLEVEL%"

@REM Write an env helper other .bat files can `call` to set HF_HOME for offline model.
> "%BUNDLE_DIR%\env.cmd" echo @echo off
>>"%BUNDLE_DIR%\env.cmd" echo set "HF_HOME=%HF_HOME%"
>>"%BUNDLE_DIR%\env.cmd" echo set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

:cleanup
if not "%_EXITCODE%"=="0" (
  echo.
  echo [FAIL] Offline gliner install exited with code %_EXITCODE%.
  if /i not "%HYBRIDRAG_NO_PAUSE%"=="1" pause >nul
) else (
  echo.
  echo [PASS] gliner installed offline.
  echo        Model cache: %HF_HOME%
  echo        Remember: export HF_HOME=%HF_HOME% in the env that runs extraction,
  echo        or the runtime will try to fetch from huggingface.co and fail.
  if /i not "%HYBRIDRAG_NO_PAUSE%"=="1" pause >nul
)
if defined _PREV_CP chcp %_PREV_CP% >nul 2>&1
endlocal & exit /b %_EXITCODE%
