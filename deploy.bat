@echo off
REM QuantSight Cloud Run Deployment (Windows)
REM Usage: deploy.bat
REM Run from quantsight_cloud_build\ directory

echo ===================================
echo  QUANTSIGHT CLOUD RUN DEPLOY
echo ===================================
echo.

set PROJECT_ID=quantsight-prod
set REGION=us-central1
set SERVICE_NAME=quantsight-cloud
set SOURCE_DIR=backend

echo Configuration:
echo    Project:  %PROJECT_ID%
echo    Region:   %REGION%
echo    Service:  %SERVICE_NAME%
echo    Source:   %SOURCE_DIR%
echo.

REM Verify source directory
if not exist "%SOURCE_DIR%\main.py" (
    echo ERROR: main.py not found in %SOURCE_DIR%\
    echo Run this script from quantsight_cloud_build\ directory
    exit /b 1
)

REM Pre-flight syntax check
echo Pre-flight syntax check...
python -m py_compile "%SOURCE_DIR%\vanguard\ai\ai_analyzer.py" 2>nul || (echo SYNTAX ERROR in ai_analyzer.py & exit /b 1)
python -m py_compile "%SOURCE_DIR%\vanguard\api\admin_routes.py" 2>nul || (echo SYNTAX ERROR in admin_routes.py & exit /b 1)
python -m py_compile "%SOURCE_DIR%\vanguard\inquisitor\middleware.py" 2>nul || (echo SYNTAX ERROR in middleware.py & exit /b 1)
echo Syntax OK
echo.

REM Set project
echo Setting project...
gcloud config set project %PROJECT_ID% --quiet
echo.

REM Deploy
echo Deploying to Cloud Run (5-7 minutes)...
echo.

gcloud run deploy %SERVICE_NAME% ^
  --source %SOURCE_DIR% ^
  --region %REGION% ^
  --platform managed ^
  --allow-unauthenticated ^
  --set-env-vars FIREBASE_PROJECT_ID=%PROJECT_ID% ^
  --memory 512Mi ^
  --timeout 300 ^
  --max-instances 10 ^
  --quiet

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo DEPLOY FAILED - check logs with: gcloud logging read --limit 50
    exit /b 1
)

echo.
echo ===================================
echo  DEPLOY COMPLETE
echo ===================================
echo.

REM Get URL
for /f "tokens=*" %%i in ('gcloud run services describe %SERVICE_NAME% --region %REGION% --format="value(status.url)"') do set SERVICE_URL=%%i
echo Service URL: %SERVICE_URL%
echo.
echo Next steps:
echo    1. Smoke test:  python scripts/smoke_test_vanguard.py %SERVICE_URL%
echo    2. Monitor logs: gcloud logging tail "resource.type=cloud_run_revision" --limit 50
echo.
