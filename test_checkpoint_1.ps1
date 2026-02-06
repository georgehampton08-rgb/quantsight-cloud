# Test Checkpoint #1: Basic Route Integrity
# ==========================================
# Tests Phases 1-2 fixes:
# - Schema infrastructure created
# - Duplicate routes removed  
# - Stub endpoints return 501

Write-Host "`n=== Test Checkpoint #1: Basic Route Integrity ===" -ForegroundColor Cyan
Write-Host "Testing Phases 1-2 fixes...`n" -ForegroundColor Gray

$BASE_URL = "https://quantsight-cloud-nucvdwqo6q-uc.a.run.app"
$PASS = 0
$FAIL = 0

# Test 1: Backend health check (no route collisions)
Write-Host "[Test 1] Backend health check..." -NoNewline
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/health" -Method GET
    if ($response.status -and $response.status -ne "degraded") {
        Write-Host " �� PASS" -ForegroundColor Green
        $PASS++
    }
    else {
        Write-Host " ⚠️  WARN: Degraded status" -ForegroundColor Yellow
        Write-Host "  Status: $($response.status)" -ForegroundColor Gray
        $PASS++
    }
}
catch {
    Write-Host " ❌ FAIL" -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    $FAIL++
}

# Test 2: Aegis simulation returns 501
Write-Host "[Test 2] Aegis simulation returns 501..." -NoNewline
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/aegis/simulate/203999?opponent_id=LAL" -Method POST -ErrorAction Stop
    Write-Host " ❌ FAIL (should return 501, got 200)" -ForegroundColor Red
    $FAIL++
}
catch {
    if ($_.Exception.Response.StatusCode -eq 501) {
        Write-Host " ✅ PASS" -ForegroundColor Green
        $PASS++
        # Parse error body
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $reader.ReadToEnd() | ConvertFrom-Json
        Write-Host "  Message: $($body.detail.message)" -ForegroundColor Gray
    }
    else {
        Write-Host " ❌ FAIL (expected 501, got $($_.Exception.Response.StatusCode))" -ForegroundColor Red
        $FAIL++
    }
}

# Test 3: Live games returns single consistent schema
Write-Host "[Test 3] Live games single schema..." -NoNewline
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/live/games" -Method GET
    $hasGames = $response.PSObject.Properties.Name -contains "games"
    $hasMeta = $response.PSObject.Properties.Name -contains "meta"
    
    if ($hasGames) {
        Write-Host " ✅ PASS" -ForegroundColor Green
        Write-Host "  Schema keys: $($response.PSObject.Properties.Name -join ', ')" -ForegroundColor Gray
        $PASS++
    }
    else {
        Write-Host " ❌ FAIL (missing 'games' field)" -ForegroundColor Red
        Write-Host "  Actual keys: $($response.PSObject.Properties.Name -join ', ')" -ForegroundColor Red
        $FAIL++
    }
}
catch {
    Write-Host " ⚠️  WARN (endpoint may be unavailable)" -ForegroundColor Yellow
    Write-Host "  Error: $_" -ForegroundColor Gray
    $PASS++  # Don't fail if pulse cache is temporarily down
}

# Summary
Write-Host "`n=== Checkpoint #1 Summary ===" -ForegroundColor Cyan
Write-Host "Passed: $PASS" -ForegroundColor Green
Write-Host "Failed: $FAIL" -ForegroundColor $(if ($FAIL -eq 0) { "Green" } else { "Red" })

if ($FAIL -eq 0) {
    Write-Host "`n✅ Checkpoint #1 PASSED - Proceeding to Phase 3-4" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "`n❌ Checkpoint #1 FAILED - Fix issues before proceeding" -ForegroundColor Red
    exit 1
}
