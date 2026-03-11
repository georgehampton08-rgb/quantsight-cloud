@echo off
REM QuantSight Cloud Run Deployment - from backend/ dir
REM Last updated: 2026-03-05
REM Run from: quantsight_cloud_build\backend\ directory
REM NOTE: Prefer running deploy.bat from quantsight_cloud_build\ root instead.

echo ===================================================
echo   QUANTSIGHT CLOUD RUN DEPLOY (min-instances=1)
echo ===================================================
echo.

set PROJECT_ID=quantsight-prod
set REGION=us-central1
set SERVICE_NAME=quantsight-cloud

echo Setting project...
gcloud config set project %PROJECT_ID% --quiet
if %ERRORLEVEL% NEQ 0 (echo ERROR: Could not set project & exit /b 1)
echo.

if not exist "main.py" (
    echo ERROR: main.py not found. Run from backend\ directory.
    exit /b 1
)

echo Pre-flight syntax check...
python -m py_compile main.py 2>nul || (echo SYNTAX ERROR: main.py & exit /b 1)
echo Syntax OK
echo.

echo Deploying to Cloud Run (5-8 minutes, --no-traffic)...

gcloud run deploy %SERVICE_NAME% ^
  --source . ^
  --region %REGION% ^
  --platform managed ^
  --allow-unauthenticated ^
  --min-instances 1 ^
  --max-instances 10 ^
  --memory 512Mi ^
  --cpu 1 ^
  --timeout 300 ^
  --concurrency 80 ^
  --set-env-vars "VANGUARD_ENABLED=true,GRPC_ENABLE_FORK_SUPPORT=1" ^
  --update-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,GITHUB_TOKEN=GITHUB_TOKEN:latest,FIREBASE_PROJECT_ID=FIREBASE_PROJECT_ID:latest" ^
  --no-traffic ^
  --quiet

if %ERRORLEVEL% NEQ 0 (
    echo DEPLOY FAILED.
    exit /b 1
)

echo.
echo Build succeeded. New revision at 0%% traffic.
echo.
echo To shift traffic after smoke test:
echo   gcloud run services update-traffic %SERVICE_NAME% --to-latest --region %REGION%
echo.
