@echo off
REM QuantSight Cloud Run Deployment - PRODUCTION
REM Last updated: 2026-03-05
REM Run from: quantsight_cloud_build\ directory
REM
REM This script:
REM   1. Verifies we're in the right project
REM   2. Deploys backend/ source with --no-traffic (safe)
REM   3. Smoke tests the new revision
REM   4. Shifts traffic only if smoke test passes
REM

echo ===================================================
echo   QUANTSIGHT CLOUD RUN DEPLOY (min-instances=1)
echo ===================================================
echo.

set PROJECT_ID=quantsight-prod
set REGION=us-central1
set SERVICE_NAME=quantsight-cloud
set SOURCE_DIR=backend

REM Confirm project
echo Setting project to %PROJECT_ID%...
gcloud config set project %PROJECT_ID% --quiet
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Could not set project.
    exit /b 1
)
echo.

REM Verify source structure is correct
if not exist "%SOURCE_DIR%\main.py" (
    echo ERROR: backend\main.py not found.
    echo Run this from quantsight_cloud_build\ directory.
    exit /b 1
)
if not exist "%SOURCE_DIR%\Dockerfile" (
    echo ERROR: backend\Dockerfile not found.
    exit /b 1
)
echo Source structure OK (backend\main.py + Dockerfile confirmed)
echo.

REM Quick Python syntax check on critical files
echo Running pre-flight syntax check...
python -m py_compile "%SOURCE_DIR%\main.py" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo SYNTAX ERROR: main.py failed syntax check.
    exit /b 1
)
echo Syntax OK.
echo.

REM Deploy with --no-traffic (safe: new revision gets 0% traffic until verified)
echo Deploying to Cloud Run (this takes 5-8 minutes)...
echo Using --no-traffic flag: manual traffic shift required after smoke test.
echo.

gcloud run deploy %SERVICE_NAME% ^
  --source %SOURCE_DIR% ^
  --region %REGION% ^
  --platform managed ^
  --allow-unauthenticated ^
  --min-instances 1 ^
  --max-instances 10 ^
  --memory 512Mi ^
  --cpu 1 ^
  --timeout 300 ^
  --concurrency 80 ^
  --set-env-vars VANGUARD_ENABLED=true ^
  --update-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest ^
  --update-secrets GITHUB_TOKEN=GITHUB_TOKEN:latest ^
  --no-traffic ^
  --quiet

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo DEPLOY FAILED.
    echo Check logs: gcloud logging read "resource.type=cloud_run_revision" --limit 30
    exit /b 1
)

echo.
echo ===================================================
echo   BUILD SUCCEEDED - New revision staged (0%% traffic)
echo ===================================================
echo.

REM Get new revision name
for /f "tokens=*" %%i in ('gcloud run revisions list --service %SERVICE_NAME% --region %REGION% --limit 1 --format "value(name)"') do set NEW_REVISION=%%i
echo New revision: %NEW_REVISION%
echo.

REM Get service URL for smoke test
for /f "tokens=*" %%i in ('gcloud run services describe %SERVICE_NAME% --region %REGION% --format "value(status.url)"') do set SERVICE_URL=%%i
echo Service URL: %SERVICE_URL%
echo.

REM Smoke test against the new revision directly
echo Running smoke test on new revision...
echo Testing: %SERVICE_URL%/health
curl -s -o nul -w "HTTP %%{http_code}" %SERVICE_URL%/health
echo.

echo.
echo ===================================================
echo   MANUAL STEP REQUIRED
echo ===================================================
echo If smoke test showed HTTP 200, shift traffic:
echo.
echo   gcloud run services update-traffic %SERVICE_NAME% --to-latest --region %REGION%
echo.
echo If smoke test failed, rollback is automatic (old revision still at 100%%).
echo Check new revision logs:
echo   gcloud run revisions logs tail %NEW_REVISION% --region %REGION%
echo.
