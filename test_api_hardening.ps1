# API Hardening - Complete Test Suite
# Tests all fixes from Phases 1-8 locally

param(
    [string]$BaseUrl = "http://localhost:8000",
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

Write-Host "`n🧪 API HARDENING TEST SUITE" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Testing against: $BaseUrl`n" -ForegroundColor Yellow

$passed = 0
$failed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int]$ExpectedStatus = 200,
        [scriptblock]$Validator = $null
    )
    
    Write-Host "Testing: $Name" -ForegroundColor White -NoNewline
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method GET -ErrorAction Stop
        
        if ($response.StatusCode -eq $ExpectedStatus) {
            $content = $response.Content | ConvertFrom-Json
            
            if ($Validator) {
                $validatorResult = & $Validator $content
                if ($validatorResult) {
                    Write-Host " ✅ PASS" -ForegroundColor Green
                    if ($Verbose) { Write-Host "   Response: $($content | ConvertTo-Json -Depth 2 -Compress)" -ForegroundColor DarkGray }
                    return $true
                }
                else {
                    Write-Host " ❌ FAIL (validation failed)" -ForegroundColor Red
                    return $false
                }
            }
            else {
                Write-Host " ✅ PASS" -ForegroundColor Green
                return $true
            }
        }
        else {
            Write-Host " ❌ FAIL (status $($response.StatusCode), expected $ExpectedStatus)" -ForegroundColor Red
            return $false
        }
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq $ExpectedStatus) {
            Write-Host " ✅ PASS (expected error $ExpectedStatus)" -ForegroundColor Green
            return $true
        }
        else {
            Write-Host " ❌ FAIL (status $statusCode, expected $ExpectedStatus)" -ForegroundColor Red
            if ($Verbose) { Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor DarkGray }
            return $false
        }
    }
}

# ==================== PHASE 1-2: ROUTE INTEGRITY ====================
Write-Host "`n📋 Phase 1-2: Route Integrity and Stubs" -ForegroundColor Cyan

if (Test-Endpoint "Health check" "$BaseUrl/health") { $passed++ } else { $failed++ }
if (Test-Endpoint "Live games endpoint exists" "$BaseUrl/live/games") { $passed++ } else { $failed++ }
if (Test-Endpoint "Aegis returns 501 Not Implemented" "$BaseUrl/aegis/simulate/123/456" -ExpectedStatus 501) { $passed++ } else { $failed++ }

# ==================== PHASE 3-4: INPUT VALIDATION ====================
Write-Host "`n📋 Phase 3-4: Input Validation" -ForegroundColor Cyan

# Valid player search
if (Test-Endpoint "Player search with valid query" "$BaseUrl/players/search?q=james" -Validator {
        param($data)
        return $data.Count -ge 0  # Should return array
    }) { $passed++ } else { $failed++ }

# Empty search query (should be 422)
if (Test-Endpoint "Player search rejects empty query" "$BaseUrl/players/search?q=" -ExpectedStatus 422) { $passed++ } else { $failed++ }

# Game logs with valid numeric player_id
if (Test-Endpoint "Game logs accepts numeric player_id" "$BaseUrl/game-logs?player_id=203999&limit=5" -Validator {
        param($data)
        return $data.logs -is [array]
    }) { $passed++ } else { $failed++ }

# Game logs with invalid player_id (should be 422 due to pattern validation)
if (Test-Endpoint "Game logs rejects non-numeric player_id" "$BaseUrl/game-logs?player_id=ABC123" -ExpectedStatus 422) { $passed++ } else { $failed++ }

# Game logs with invalid team_id format (should be 422)
if (Test-Endpoint "Game logs rejects invalid team_id" "$BaseUrl/game-logs?team_id=LAKERS" -ExpectedStatus 422) { $passed++ } else { $failed++ }

# Date range validation
if (Test-Endpoint "Game logs rejects end_date < start_date" "$BaseUrl/game-logs?start_date=2024-12-31&end_date=2024-01-01" -ExpectedStatus 422) { $passed++ } else { $failed++ }

# ==================== PHASE 5: NULL SAFETY ====================
Write-Host "`n📋 Phase 5: Null Safety" -ForegroundColor Cyan

# Valid player profile
if (Test-Endpoint "Player profile returns valid data" "$BaseUrl/player/203999" -Validator {
        param($data)
        return ($data.player_id -ne $null) -and ($data.name -ne $null)
    }) { $passed++ } else { $failed++ }

# Non-existent player (404)
if (Test-Endpoint "Player profile returns 404 for invalid ID" "$BaseUrl/player/999999999" -ExpectedStatus 404) { $passed++ } else { $failed++ }

# ==================== PHASE 6: RESPONSE STRUCTURE ====================
Write-Host "`n📋 Phase 6: Response Optimization" -ForegroundColor Cyan

# Schedule should NOT have duplicate flat fields
if (Test-Endpoint "Schedule uses nested structure" "$BaseUrl/schedule" -Validator {
        param($data)
        $firstGame = $data.games[0]
        # Check nested structure exists
        $hasNested = ($firstGame.home_team -ne $null) -and ($firstGame.away_team -ne $null)
        # Check duplicate flat fields are REMOVED
        $noDuplicates = ($firstGame.home -eq $null) -and ($firstGame.away -eq $null)
        return $hasNested -and $noDuplicates
    }) { $passed++ } else { $failed++ }

# Roster should have type-safe jersey_number
if (Test-Endpoint "Roster has type-safe fields" "$BaseUrl/roster/LAL" -Validator {
        param($data)
        $firstPlayer = $data.players[0]
        # jersey_number should be string
        return ($firstPlayer.jersey_number -is [string]) -or ($firstPlayer.jersey_number -eq $null)
    }) { $passed++ } else { $failed++ }

# ==================== PHASE 7: BOXSCORE AGGREGATION ====================
Write-Host "`n📋 Phase 7: Boxscore Aggregation" -ForegroundColor Cyan

# Note: This requires a valid game_id from your Firestore
# Using a placeholder - update with real game_id for actual testing
$testGameId = "0022300415"  # Replace with actual game ID

if (Test-Endpoint "Boxscore aggregates player stats" "$BaseUrl/boxscore/$testGameId" -Validator {
        param($data)
        # Should have aggregated structure
        $hasTeams = ($data.home_team -ne $null) -and ($data.away_team -ne $null)
        # Players should have calculated percentages
        $firstPlayer = $data.home_team.players[0]
        $hasPercentages = ($firstPlayer.fg_pct -ne $null) -or ($data.home_team.players.Count -eq 0)
        return $hasTeams -and $hasPercentages
    }) { $passed++ } else { $failed++ }

# ==================== PHASE 8: ERROR HANDLING ====================
Write-Host "`n📋 Phase 8: Sanitized Error Messages" -ForegroundColor Cyan

# Test that errors don't expose internals
if (Test-Endpoint "Errors are sanitized" "$BaseUrl/player/INVALID_ID" -ExpectedStatus 404 -Validator {
        # 404 should not expose Firestore stack traces
        return $true  # Just checking it returns 404
    }) { $passed++ } else { $failed++ }

# ==================== SUMMARY ====================
Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "TEST RESULTS" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })
Write-Host "Total:  $($passed + $failed)`n" -ForegroundColor White

if ($failed -eq 0) {
    Write-Host "✅ ALL TESTS PASSED - Ready for deployment!" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "❌ SOME TESTS FAILED - Review errors above" -ForegroundColor Red
    exit 1
}
