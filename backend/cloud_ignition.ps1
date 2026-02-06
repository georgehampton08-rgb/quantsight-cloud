# QuantSight Cloud Backend - Local Ignition Script
# ==================================================
# PowerShell script to set up isolated environment and smoke test

Write-Host "QuantSight Cloud Backend - Local Ignition" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create isolated Python virtual environment
Write-Host "[1/5] Creating Python virtual environment..." -ForegroundColor Yellow

$venvPath = ".\venv_cloud"

if (Test-Path $venvPath) {
    Write-Host "   Virtual environment already exists, removing..." -ForegroundColor Gray
    Remove-Item -Recurse -Force $venvPath
}

python -m venv $venvPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED to create virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host "   DONE: Virtual environment created: $venvPath" -ForegroundColor Green
Write-Host ""

# Step 2: Activate virtual environment
Write-Host "[2/5] Activating virtual environment..." -ForegroundColor Yellow

& "$venvPath\Scripts\Activate.ps1"

Write-Host "   DONE: Virtual environment activated" -ForegroundColor Green
Write-Host ""

# Step 3: Install dependencies
Write-Host "[3/5] Installing dependencies from backend/requirements.txt..." -ForegroundColor Yellow

python -m pip install --upgrade pip --quiet
pip install -r backend\requirements.txt --quiet
pip install pytest --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED to install dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "   DONE: Dependencies installed" -ForegroundColor Green
Write-Host ""

# Step 4: Create .env.cloud for local testing
Write-Host "[4/5] Generating .env.cloud with SQLite fallback..." -ForegroundColor Yellow

$envPath = "backend\.env.cloud"
$envLines = @(
    "# Cloud Backend - Local Testing Environment",
    "# ==========================================",
    "",
    "# Database: SQLite for local testing",
    "DATABASE_URL=sqlite:///./backend/data/cloud_test.db",
    "",
    "# Firebase: Mock credentials (will gracefully degrade)",
    "FIREBASE_PROJECT_ID=local-test-project",
    "GOOGLE_APPLICATION_CREDENTIALS=./mock_credentials.json",
    "",
    "# API Configuration",
    "PORT=8080",
    "ALLOWED_ORIGINS=*",
    "",
    "# Logging",
    "LOG_LEVEL=INFO"
)

$envLines | Out-File -FilePath $envPath -Encoding utf8

Write-Host "   DONE: .env.cloud created with SQLite configuration" -ForegroundColor Green
Write-Host ""

# Step 5: Create data directory
Write-Host "[5/5] Creating backend/data directory..." -ForegroundColor Yellow

New-Item -ItemType Directory -Path "backend\data" -Force | Out-Null

Write-Host "   DONE: Data directory ready" -ForegroundColor Green
Write-Host ""

# Run startup test
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Running Smoke Test..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Add backend to PYTHONPATH
$currentDir = Get-Location
$env:PYTHONPATH = "$currentDir\backend;$currentDir\shared_core"

Write-Host "PYTHONPATH set to: $env:PYTHONPATH" -ForegroundColor Gray
Write-Host ""

# Run pytest
Write-Host "Executing: pytest backend/tests/test_startup.py -v" -ForegroundColor Gray
Write-Host ""

Set-Location backend
pytest tests\test_startup.py -v --tb=short

$testResult = $LASTEXITCODE
Set-Location ..

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan

if ($testResult -eq 0) {
    Write-Host "SUCCESS: SMOKE TEST PASSED - Cloud backend is operational!" -ForegroundColor Green
}
else {
    Write-Host "FAILED: SMOKE TEST FAILED - See errors above" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  - Missing shared_core imports: Check PYTHONPATH" -ForegroundColor Gray
    Write-Host "  - Missing dependencies: Re-run pip install" -ForegroundColor Gray
    Write-Host "  - Router import errors: Check app/routers/__init__.py" -ForegroundColor Gray
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Keep virtual environment activated for manual testing
Write-Host "NOTE: Virtual environment remains activated for manual testing" -ForegroundColor Cyan
Write-Host "   To start server manually: cd backend; python -m uvicorn main:app --reload" -ForegroundColor Gray
Write-Host ""

exit $testResult
