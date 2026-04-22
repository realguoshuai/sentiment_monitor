@echo off
setlocal

echo ======================================================
echo   Sentiment Monitor V2.5 - High Performance Startup
echo ======================================================

:: 1. Start Backend (Uvicorn ASGI)
echo [1/4] Starting Uvicorn Backend Engine...
start "Sentiment-Backend" cmd /k "cd /d "%~dp0backend" && call .\venv\Scripts\activate.bat && set ENABLE_STARTUP_WARM=1 && uvicorn sentiment_monitor.asgi:application --host 127.0.0.1 --port 8000"

:: 2. Start Frontend (Vite/Vue3)
echo [2/4] Starting Vue3 Frontend...
start "Sentiment-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: 3. Wait and Open Browser
echo [3/4] Waiting for services (5s)...
ping 127.0.0.1 -n 6 > nul
start "" "http://localhost:5173"

:: 4. Finish
echo [4/4] Services are up.

echo.
echo ======================================================
echo   Startup script finished.
echo   [Upgraded] Backend is now powered by Uvicorn ASGI.
echo   [Upgraded] SQLite concurrent WAL mode is active.
echo ======================================================
pause
