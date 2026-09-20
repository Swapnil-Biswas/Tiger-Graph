# TigerGraph Agentic Fraud Investigator - Fast Smoke Test (Windows PowerShell)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "=== Running TigerGraph Fraud Investigator Smoke Test ===" -ForegroundColor Cyan
python "$ScriptDir\smoke_test.py" $args
if ($LASTEXITCODE -ne 0) {
    Write-Host "Smoke test failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
