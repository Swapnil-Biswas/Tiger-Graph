# ==============================================================================
# TigerGraph Agentic Fraud Investigator - Full Verification Runner (PowerShell)
# ==============================================================================
param (
    [switch]$Serve = $false,
    [switch]$Quick = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  TigerGraph Agentic Fraud Investigator: Full Pipeline Runner     " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Environment and Clean Clone Sanity Check
Write-Host "`n--> Running Sanity & Verification Check..." -ForegroundColor Yellow
if ($Quick) {
    python scripts/verify_install.py --quick
} else {
    python scripts/verify_install.py
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Sanity check failed."
    exit 1
}

# 2. Schema Validation
Write-Host "`n--> Running Benchmark Schema Validator (eval/validate_answers.py)..." -ForegroundColor Yellow
python eval/validate_answers.py cases/
if ($LASTEXITCODE -ne 0) {
    Write-Error "Schema validation failed."
    exit 1
}

# 3. Unit Test Suite
Write-Host "`n--> Running Unit Tests..." -ForegroundColor Yellow
python -m unittest tests/test_phase4.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Unit tests failed."
    exit 1
}

# 4. Optional: Start FastAPI server if -Serve is specified
if ($Serve) {
    Write-Host "`n--> Launching FastAPI Server on http://0.0.0.0:8000..." -ForegroundColor Green
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
}

Write-Host "`n--> All stages executed successfully!" -ForegroundColor Green
