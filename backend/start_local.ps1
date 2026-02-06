# Quick Start - Local Testing
# Run this in PowerShell from the backend directory

Write-Host "`n🚀 Starting QuantSight Backend Locally..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check if in correct directory
if (-not (Test-Path "main.py")) {
    Write-Host "❌ Error: main.py not found. Please run from backend\ directory" -ForegroundColor Red
    exit 1
}

# Check Python version
$pythonVersion = python --version 2>&1
Write-Host "✅ $pythonVersion" -ForegroundColor Green

# Check dependencies
Write-Host "`n📦 Checking dependencies..." -ForegroundColor Yellow
try {
    python -c "import fastapi, uvicorn" 2>$null
    Write-Host "✅ FastAPI & Uvicorn installed" -ForegroundColor Green
}
catch {
    Write-Host "❌ Installing FastAPI..." -ForegroundColor Red
    pip install fastapi uvicorn python-dotenv
}

# Set environment
$env:PORT = "8000"
$env:ENV = "development"

Write-Host "`n🔥 Starting server on http://localhost:8000" -ForegroundColor Green
Write-Host "   Health: http://localhost:8000/health" -ForegroundColor White
Write-Host "   Live Games: http://localhost:8000/live/games" -ForegroundColor White
Write-Host "`n   Press Ctrl+C to stop`n" -ForegroundColor Yellow

# Start uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level info
