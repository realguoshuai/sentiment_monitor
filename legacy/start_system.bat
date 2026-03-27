@echo off
chcp 65001 >nul
title Sentiment Monitor - Starter

echo ========================================
echo    Sentiment Monitor System
echo ========================================
echo.

:: Set working directory
cd /d "%~dp0"

:: Check backend directory
if not exist "backend\manage.py" (
    echo [ERROR] Backend project not found!
    pause
    exit /b 1
)

:: Check frontend directory
if not exist "frontend\package.json" (
    echo [ERROR] Frontend project not found!
    pause
    exit /b 1
)

echo [*] Starting Django backend...
start "Backend Service" cmd /k "cd backend && venv\Scripts\activate && echo [+] Django activated && python manage.py runserver 0.0.0.0:8000"

echo [*] Waiting for backend...
timeout /t 5 /nobreak >nul

echo [*] Starting Vue frontend...
start "Frontend Service" cmd /k "cd frontend && echo [+] Starting dev server && npm run dev"

echo [*] Waiting for frontend...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo [OK] All services started!
echo ========================================
echo.
echo Access URLs:
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000/api/
echo.
echo Data Collection:
echo   cd backend ^&^& python collector/collector.py
echo.
echo Press any key to stop all services...
pause >nul

:: Stop all service windows
taskkill /FI "WINDOWTITLE eq Backend Service*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Frontend Service*" /F >nul 2>&1

echo [OK] Services stopped
timeout /t 2 >nul
