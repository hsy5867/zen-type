@echo off
REM zen-type Windows launcher
REM Requires: uv (https://docs.astral.sh/uv/)

cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv not found. Install from: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [zen-type] First run - installing dependencies via uv sync...
    uv sync
    if errorlevel 1 (
        echo [ERROR] uv sync failed.
        pause
        exit /b 1
    )
)

echo [zen-type] Starting...
uv run zen-type %*
