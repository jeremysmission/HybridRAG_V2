@echo off
title HybridRAG V2 Lane 2 GUI Harness
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if not defined CUDA_VISIBLE_DEVICES set "CUDA_VISIBLE_DEVICES=1"
set "HYBRIDRAG_GUI_HARNESS_NAME=guiharness_lane2"
set "HYBRIDRAG_GUI_HARNESS_ROLE=Agent B"

echo [INFO] Launching Lane 2 GUI harness from "%CD%"
echo [INFO] Role: Agent B
echo [INFO] GPU:  CUDA_VISIBLE_DEVICES=%CUDA_VISIBLE_DEVICES%
echo [INFO] Harness: %HYBRIDRAG_GUI_HARNESS_NAME%
call "%~dp0start_qa_workbench.bat" %*
