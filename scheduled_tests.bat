@echo off
REM QuantSight - Scheduled Endpoint Tests
REM Tests all API endpoints and logs results
REM Usage: Add to Windows Task Scheduler

echo ===================================
echo  QUANTSIGHT ENDPOINT TESTS
echo  %date% %time%
echo ===================================

cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

echo Running comprehensive endpoint tests...
python test_all_endpoints.py > logs\test_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log 2>&1

if %errorlevel% equ 0 (
    echo SUCCESS - All tests passed
) else (
    echo WARNING - Some tests may have failed
)

echo ===================================
pause
