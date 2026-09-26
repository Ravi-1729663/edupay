# =====================================================================
# EduPay — Local Launcher Script (Windows PowerShell)
# =====================================================================

Write-Host "==========================================================" -ForegroundColor DarkGreen
Write-Host "  EduPay - Fee Collection and Financial Reconciliation System " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor DarkGreen

$Root = Get-Location

# Default local database to SQLite unless PostgreSQL is explicitly specified
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "sqlite:///$Root\backend\edupay_local.db"
}

# 1. Check Python
Write-Host ""
Write-Host "[1/4] Checking Python environment..." -ForegroundColor Yellow
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Setup Backend Dependencies & DB
Write-Host "[2/4] Setting up Backend dependencies and database..." -ForegroundColor Yellow
Set-Location "$Root\backend"
python -m pip install -q -r requirements.txt 2>$null

Write-Host "Running database migrations..." -ForegroundColor Gray
python -m alembic upgrade head
Write-Host "Seeding database with realistic demo dataset..." -ForegroundColor Gray
python -m app.db.seed

Set-Location $Root

# 3. Check Node.js & Install Frontend Dependencies
Write-Host ""
Write-Host "[3/4] Checking Node.js environment..." -ForegroundColor Yellow
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Node.js / npm is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "$Root\node_modules")) {
    Write-Host "Installing frontend node dependencies..." -ForegroundColor Gray
    npm install
}

# 4. Launching Backend & Frontend
Write-Host ""
Write-Host "[4/4] Launching EduPay Services..." -ForegroundColor Yellow
Write-Host "  Backend API:  http://localhost:8000  (Docs: http://localhost:8000/docs)" -ForegroundColor Cyan
Write-Host "  Frontend SPA: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Demo Accounts (Password: Password123!):" -ForegroundColor Green
Write-Host "  - System Admin:      admin@edupay.college" -ForegroundColor White
Write-Host "  - Finance Manager:   manager@edupay.college" -ForegroundColor White
Write-Host "  - Finance Staff:     staff@edupay.college" -ForegroundColor White
Write-Host "  - Student:           student@edupay.college" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor DarkGreen

# Launch FastAPI Backend in background job
$BackendJob = Start-Job -ScriptBlock {
    param($path, $db_url)
    $env:DATABASE_URL = $db_url
    Set-Location $path
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} -ArgumentList "$Root\backend", $env:DATABASE_URL

# Launch Frontend in foreground
try {
    npm run dev
}
finally {
    Write-Host ""
    Write-Host "Stopping backend process..." -ForegroundColor Yellow
    Stop-Job $BackendJob
    Remove-Job $BackendJob
}
