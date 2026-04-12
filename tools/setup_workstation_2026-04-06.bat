@echo off
title HybridRAG V2 Workstation Setup (2026-04-06 compatibility shim)
setlocal EnableExtensions
cd /d "%~dp0"

set "SCRIPT=%~dp0setup_workstation_2026-04-12.bat"

if not exist "%SCRIPT%" (
  echo [FAIL] Current dated setup wrapper not found:
  echo        %SCRIPT%
  if /I not "%HYBRIDRAG_NO_PAUSE%"=="1" pause
  exit /b 1
)

echo [INFO] setup_workstation_2026-04-06.bat is a compatibility shim.
echo [INFO] Current dated launcher: %SCRIPT%
call "%SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
