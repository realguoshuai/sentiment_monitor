# Sentiment Monitor System Starter
# Save as start.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Sentiment Monitor System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set working directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Check backend
if (-not (Test-Path "backend\manage.py")) {
    Write-Host "[ERROR] Backend project not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check frontend
if (-not (Test-Path "frontend\package.json")) {
    Write-Host "[ERROR] Frontend project not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[*] Starting Django backend..." -ForegroundColor Yellow
$backendJob = Start-Process -FilePath "cmd.exe" -ArgumentList "/k cd backend && venv\Scripts\activate && python manage.py runserver 0.0.0.0:8000" -WindowStyle Normal -PassThru

Write-Host "[*] Waiting for backend (5s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "[*] Starting Vue frontend..." -ForegroundColor Yellow
$frontendJob = Start-Process -FilePath "cmd.exe" -ArgumentList "/k cd frontend && npm run dev" -WindowStyle Normal -PassThru

Write-Host "[*] Waiting for frontend (5s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " [OK] All services started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Backend:  http://localhost:8000/api/" -ForegroundColor White
Write-Host ""
Write-Host "Data Collection:" -ForegroundColor Yellow
Write-Host "  cd backend; venv\Scripts\activate; python collector\collector.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Enter to stop all services..." -ForegroundColor Magenta
Read-Host

# Stop services
Write-Host "[*] Stopping services..." -ForegroundColor Yellow
Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue

Write-Host "[OK] Services stopped" -ForegroundColor Green
Start-Sleep -Seconds 2
