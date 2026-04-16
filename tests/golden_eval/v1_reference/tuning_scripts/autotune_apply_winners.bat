@REM === NON-PROGRAMMER GUIDE ===
@REM Purpose: Starts one of the archived autotuning helper flows kept under test references.
@REM How to follow: Treat it as a historical or reference launcher rather than part of the mainline operator workflow.
@REM Inputs: The referenced tuning scripts and a working Python environment.
@REM Outputs: The archived tuning workflow requested by the script.
@REM ============================
@echo off
setlocal
call "%~dp0run_mode_autotune.bat" --workflow full --grid starter --mode offline --screen-limit 50 --apply-winner %*
exit /b %ERRORLEVEL%
