@echo off

echo ========================================
echo Sentiment Monitor System
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe --version
) else (
    echo ERROR: python.exe not found
    pause
    exit 1
)

echo.
echo [2/3] Running data collection...
venv\Scripts\python.exe main.py
if errorlevel 1 (
    echo Collection failed
    pause
    exit 1
)

echo.
echo [3/3] Starting web server...
echo.
echo Dashboard: http://localhost:8888/dashboard.html
echo API: http://localhost:8888/api/data
echo.
echo Press Ctrl+C to stop
echo ========================================

venv\Scripts\python.exe server.py

pause
