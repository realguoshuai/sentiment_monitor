@echo off
chcp 65001 >nul
title Close Sentiment Monitor

echo [*] Stopping all services...

:: Stop Node.js (Frontend)
taskkill /F /IM node.exe 2>nul
if %errorlevel% == 0 (
    echo [OK] Frontend stopped
) else (
    echo [INFO] Frontend not running
)

:: Stop Python (Backend)
taskkill /F /IM python.exe 2>nul
if %errorlevel% == 0 (
    echo [OK] Backend stopped
) else (
    echo [INFO] Backend not running
)

echo.
echo [OK] All services stopped
timeout /t 2 >nul
