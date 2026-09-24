# =====================================================================
# EduPay — Local Launcher Script (Windows PowerShell)
# =====================================================================

Write-Host "==========================================================" -ForegroundColor Emerald
Write-Host "  EduPay — Fee Collection & Financial Reconciliation System " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Emerald

$Root = Get-Location

# 1. Check Python
Write-Host "`n[1/4] Checking Python environment..." -ForegroundColor Yellow
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Setup Backend Dependencies & DB
Write-Host "[2/4] Setting up Backend dependencies & database..." -ForegroundColor Yellow
Set-Location "$Root\backend"
python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install Python dependencies." -ForegroundColor Red
    Set-Location $Root
    exit 1
}

Write-Host "Running database migrations..." -ForegroundColor Gray
python -m alembic upgrade head
Write-Host "Seeding database with realistic demo dataset..." -ForegroundColor Gray
python -m app.db.seed

Set-Location $Root

# 3. Check Node.js & Install Frontend Dependencies
Write-Host "`n[3/4] Checking Node.js environment..." -ForegroundColor Yellow
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Node.js / npm is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "$Root\node_modules")) {
    Write-Host "Installing frontend node dependencies..." -ForegroundColor Gray
    npm install
}

# 4. Launching Backend & Frontend
Write-Host "`n[4/4] Launching EduPay Services..." -ForegroundColor Yellow
Write-Host "  Backend API:  http://localhost:8000  (Docs: http://localhost:8000/docs)" -ForegroundColor Cyan
Write-Host "  Frontend SPA: http://localhost:3000" -ForegroundColor Cyan
Write-Host "`nDemo Accounts (Password: Password123!):" -ForegroundColor Green
Write-Host "  - System Admin:      admin@edupay.college" -ForegroundColor White
Write-Host "  - Finance Manager:   manager@edupay.college" -ForegroundColor White
Write-Host "  - Finance Staff:     staff@edupay.college" -ForegroundColor White
Write-Host "  - Student:           student@edupay.college" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Emerald

# Launch FastAPI Backend in background job
$BackendJob = Start-Job -ScriptBlock {
    param($path)
    Set-Location $path
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} -ArgumentList "$Root\backend"

# Launch Frontend in foreground
try {
    npm run dev
}
finally {
    Write-Host "`nStopping backend process..." -ForegroundColor Yellow
    Stop-Job $BackendJob
    Remove-Job $BackendJob
}
