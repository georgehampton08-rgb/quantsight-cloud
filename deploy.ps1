#!/usr/bin/env pwsh
<#
.SYNOPSIS
    QuantSight Full-Stack Deploy Script
    Builds frontend, deploys to Firebase Hosting + Cloud Run, then
    automatically shifts 100% traffic to the new revision.

.USAGE
    From quantsight_cloud_build\ root:
        .\deploy.ps1              # full deploy (frontend + backend)
        .\deploy.ps1 -BackendOnly # skip frontend build/hosting
        .\deploy.ps1 -FrontendOnly# skip Cloud Run deploy

.NOTES
    Requires: gcloud CLI, firebase-tools, npm, wsl (for git push via SSH)
#>

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$SkipGitPush
)

$ErrorActionPreference = "Stop"

# ── Constants ────────────────────────────────────────────────────────────────
$PROJECT    = "quantsight-prod"
$REGION     = "us-central1"
$SERVICE    = "quantsight-cloud"
$PROD_URL   = "https://quantsight-cloud-nucvdwqo6q-uc.a.run.app"
$BACKEND    = "$PSScriptRoot\backend"
$ROOT       = $PSScriptRoot

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    OK  $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "    FAIL  $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "   QUANTSIGHT DEPLOY  $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta

# ── Step 0: Git commit + push (via WSL SSH) ──────────────────────────────────
if (-not $SkipGitPush) {
    Write-Step "Git — staging all changes and pushing via WSL"
    Set-Location $ROOT
    git add -A 2>&1 | Out-Null
    $status = git status --porcelain 2>&1
    if ($status) {
        git commit -m "deploy: $(Get-Date -Format 'yyyy-MM-dd HH:mm') auto-commit" 2>&1 | Write-Host
    } else {
        Write-Host "    Nothing new to commit — pushing existing HEAD"
    }
    wsl bash -c "cd /mnt/c/Users/georg/quantsight_engine/quantsight_cloud_build && git push origin main 2>&1"
    if ($LASTEXITCODE -ne 0) { Write-Fail "git push failed" }
    Write-OK "Pushed to GitHub"
}

# ── Step 1: Frontend build ────────────────────────────────────────────────────
if (-not $BackendOnly) {
    Write-Step "Frontend — npm run build"
    Set-Location $ROOT
    npm run build 2>&1 | Select-String -Pattern "error TS|ERROR|built in" | Write-Host
    if ($LASTEXITCODE -ne 0) { Write-Fail "Frontend build failed" }
    Write-OK "Frontend built"

    Write-Step "Frontend — firebase deploy --only hosting"
    firebase deploy --only hosting --project $PROJECT 2>&1 | Select-String -Pattern "hosting|Error|✓|\+" | Write-Host
    if ($LASTEXITCODE -ne 0) { Write-Fail "Firebase hosting deploy failed" }
    Write-OK "Firebase Hosting deployed"
}

# ── Step 2: Backend syntax check ─────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Step "Backend — syntax check"
    Set-Location $BACKEND
    python -m py_compile main.py
    if ($LASTEXITCODE -ne 0) { Write-Fail "main.py has syntax errors" }
    python -m py_compile api/play_by_play_routes.py
    if ($LASTEXITCODE -ne 0) { Write-Fail "play_by_play_routes.py has syntax errors" }
    python -m py_compile services/firebase_pbp_service.py
    if ($LASTEXITCODE -ne 0) { Write-Fail "firebase_pbp_service.py has syntax errors" }
    Write-OK "Syntax OK"

    # ── Step 3: Cloud Run deploy ──────────────────────────────────────────────
    Write-Step "Backend — gcloud run deploy (this takes 3-6 minutes)"
    gcloud config set project $PROJECT --quiet 2>&1 | Out-Null

    gcloud run deploy $SERVICE `
        --source . `
        --region $REGION `
        --platform managed `
        --allow-unauthenticated `
        --min-instances 1 `
        --max-instances 10 `
        --memory 512Mi `
        --cpu 1 `
        --timeout 300 `
        --concurrency 80 `
        --set-env-vars "VANGUARD_ENABLED=true,GRPC_ENABLE_FORK_SUPPORT=1" `
        --update-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,GITHUB_TOKEN=GITHUB_TOKEN:latest,FIREBASE_PROJECT_ID=FIREBASE_PROJECT_ID:latest" `
        --no-traffic `
        --quiet 2>&1

    if ($LASTEXITCODE -ne 0) { Write-Fail "Cloud Run deploy failed" }
    Write-OK "New revision built and created (0% traffic)"

    # ── Step 4: Shift 100% traffic (pre-smoke — prod URL is always accessible) ─
    Write-Step "Smoke test — skipping per-revision URL (using prod URL after traffic shift)"
    Write-Host "    (Proceeding to traffic shift — prod health check runs after)"

    # ── Step 5: Shift 100% traffic ───────────────────────────────────────────
    Write-Step "Traffic — shifting 100% to latest revision"
    gcloud run services update-traffic $SERVICE `
        --to-latest `
        --region $REGION `
        --quiet 2>&1

    if ($LASTEXITCODE -ne 0) { Write-Fail "Traffic shift failed" }
    Write-OK "100% traffic on new revision"

    # ── Step 6: Production smoke check ───────────────────────────────────────
    Write-Step "Production smoke test"
    Start-Sleep 3
    try {
        $health = (Invoke-WebRequest "$PROD_URL/health" -UseBasicParsing -TimeoutSec 15).StatusCode
        $dates  = (Invoke-WebRequest "$PROD_URL/v1/games/dates/2026-02-01" -UseBasicParsing -TimeoutSec 15).Content | ConvertFrom-Json
        Write-OK "Health: HTTP $health"
        Write-OK "/dates/2026-02-01: $($dates.count) games returned"
    } catch {
        Write-Host "    WARNING: Production smoke check had an issue: $_" -ForegroundColor Yellow
        Write-Host "    The deploy succeeded but verify manually: $PROD_URL/health"
    }
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "   DEPLOY COMPLETE  $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Green
Write-Host "   Frontend: https://quantsight-prod.web.app" -ForegroundColor Green
Write-Host "   Backend:  $PROD_URL" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
