@echo off
setlocal
echo [INFO] HybridRAG V2 Beast Setup
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_beast_2026-04-05.ps1"
pause
endlocal
