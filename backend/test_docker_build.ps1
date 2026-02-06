# QuantSight Cloud Backend - Local Docker Build Test
# ====================================================
# Tests Docker image build and container startup

Write-Host "Docker Build & Test Script" -ForegroundColor Cyan
Write-Host "===========================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$imageName = "quantsight-cloud"
$containerName = "quantsight-cloud-test"
$port = 8080

# Step 1: Build Docker image
Write-Host "[1/4] Building Docker image..." -ForegroundColor Yellow
Write-Host "   Context: . (quantsight_cloud_build root)" -ForegroundColor Gray
Write-Host "   Dockerfile: backend/Dockerfile" -ForegroundColor Gray
Write-Host ""

docker build -t $imageName -f backend/Dockerfile .

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Docker build failed" -ForegroundColor Red
    exit 1
}

Write-Host "   DONE: Image built successfully" -ForegroundColor Green
Write-Host ""

# Step 2: Stop and remove existing container (if any)
Write-Host "[2/4] Cleaning up old containers..." -ForegroundColor Yellow

docker stop $containerName 2>$null | Out-Null
docker rm $containerName 2>$null | Out-Null

Write-Host "   DONE: Cleanup complete" -ForegroundColor Green
Write-Host ""

# Step 3: Run container with test environment
Write-Host "[3/4] Starting container on port ${port}..." -ForegroundColor Yellow

docker run -d `
    --name $containerName `
    -p ${port}:8080 `
    -e DATABASE_URL="sqlite:////app/data/cloud_test.db" `
    -e FIREBASE_PROJECT_ID="local-test-project" `
    -e LOG_LEVEL="INFO" `
    $imageName

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Container failed to start" -ForegroundColor Red
    exit 1
}

Write-Host "   DONE: Container started (ID: $containerName)" -ForegroundColor Green
Write-Host ""

# Wait for container to be ready
Write-Host "   Waiting for container to initialize..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Step 4: Health check
Write-Host "[4/4] Testing health endpoint..." -ForegroundColor Yellow

$maxRetries = 5
$retryCount = 0
$healthCheckPassed = $false

while ($retryCount -lt $maxRetries -and -not $healthCheckPassed) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:${port}/health" -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            $healthCheckPassed = $true
            Write-Host "   SUCCESS: Health check passed (200 OK)" -ForegroundColor Green
            Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
        }
    }
    catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "   Retry $retryCount/$maxRetries..." -ForegroundColor Gray
            Start-Sleep -Seconds 2
        }
    }
}

Write-Host ""

# Step 5: Check container logs
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Container Logs (last 20 lines):" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
docker logs $containerName --tail 20
Write-Host ""

# Step 6: Verify shared_core import
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Checking shared_core availability..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

docker exec $containerName python -c "import sys; print('PYTHONPATH:', sys.path); from shared_core.engines.pie_calculator import calculate_live_pie; print('SUCCESS: shared_core imported!')" 2>&1

$sharedCoreCheck = $LASTEXITCODE

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

if ($healthCheckPassed -and $sharedCoreCheck -eq 0) {
    Write-Host "SUCCESS: All tests passed!" -ForegroundColor Green
    Write-Host "  - Docker build: OK" -ForegroundColor Gray
    Write-Host "  - Container startup: OK" -ForegroundColor Gray
    Write-Host "  - Health endpoint: OK" -ForegroundColor Gray
    Write-Host "  - shared_core import: OK" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Container is running at: http://localhost:${port}" -ForegroundColor Cyan
    Write-Host "To view logs: docker logs $containerName -f" -ForegroundColor Gray
    Write-Host "To stop: docker stop $containerName" -ForegroundColor Gray
    $exitCode = 0
}
else {
    Write-Host "FAILED: Some tests failed" -ForegroundColor Red
    if (-not $healthCheckPassed) {
        Write-Host "  - Health check: FAILED" -ForegroundColor Red
    }
    if ($sharedCoreCheck -ne 0) {
        Write-Host "  - shared_core import: FAILED" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "To debug: docker logs $containerName" -ForegroundColor Yellow
    $exitCode = 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

exit $exitCode
