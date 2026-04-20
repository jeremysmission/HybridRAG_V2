@echo off
setlocal
set ROOT=%~dp0
cd /d "%ROOT%"
"%ROOT%.venv\Scripts\python.exe" "%ROOT%tools\qa\query_panel_live_harness.py" --mode real %*
set EXIT_CODE=%ERRORLEVEL%
endlocal & exit /b %EXIT_CODE%
