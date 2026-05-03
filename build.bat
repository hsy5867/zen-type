@echo off
REM Build zen-type into a single-file Windows exe.

cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv not found. Install from: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

echo [build] syncing build dependencies...
uv sync --extra build
if errorlevel 1 (
    echo [ERROR] uv sync failed.
    pause
    exit /b 1
)

echo [build] packaging...
uv run python build.py %*
if errorlevel 1 (
    echo [ERROR] build failed.
    pause
    exit /b 1
)

echo.
echo [build] done — see dist\ folder.
pause
