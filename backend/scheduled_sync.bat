@echo off
REM QuantSight - Scheduled Data Sync
REM Syncs local player data to Cloud SQL daily
REM Usage: Add to Windows Task Scheduler

echo ===================================
echo  QUANTSIGHT CLOUD SYNC
echo  %date% %time%
echo ===================================

cd /d "%~dp0"

echo Running data sync...
python scripts\sync_to_cloud.py > logs\sync_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log 2>&1

if %errorlevel% equ 0 (
    echo SUCCESS - Sync completed
) else (
    echo ERROR - Sync failed with code %errorlevel%
)

echo ===================================
pause
