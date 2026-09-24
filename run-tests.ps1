# =====================================================================
# EduPay — Test Suite Launcher (Windows PowerShell)
# Runs the full backend unit, integration, and integrity test suite
# =====================================================================

Write-Host "Running EduPay Backend Test Suite (pytest)..." -ForegroundColor Yellow
$Root = Get-Location
Set-Location "$Root\backend"
python -m pytest app/tests -v
$Result = $LASTEXITCODE
Set-Location $Root
exit $Result
