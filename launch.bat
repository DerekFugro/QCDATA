@echo off
REM ============================================================
REM  QCDATA launcher (DEVELOPMENT) - double-click to start the app.
REM  On first run it sets up the Python environment with uv.
REM ============================================================
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: 'uv' was not found on your PATH.
    echo Install uv from https://docs.astral.sh/uv/ and then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\" (
    echo First run - setting up the environment. This may take a minute...
    uv sync
    if errorlevel 1 (
        echo.
        echo Environment setup failed. See the messages above.
        pause
        exit /b 1
    )
)

echo Starting QCDATA...
uv run qcdata-gui
if errorlevel 1 (
    echo.
    echo QCDATA exited with an error. See the messages above.
    pause
    exit /b 1
)

exit /b 0
