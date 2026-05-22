@echo off
chcp 65001 >nul 2>&1
title Sync Data...
cd /d "%~dp0backend"
call venv\Scripts\activate.bat
echo ========================================
echo   Sync All Data
echo ========================================
echo.
python -u manage.py sync_all_data --skip-collector
echo.
echo ========================================
echo   Done. Press any key to close.
echo ========================================
pause >nul
