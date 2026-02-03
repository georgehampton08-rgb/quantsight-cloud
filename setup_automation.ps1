# QuantSight Cloud - Automated Task Setup
# Creates Windows Task Scheduler jobs for data sync and testing

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " QUANTSIGHT AUTOMATION SETUP" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Get current directory
$scriptDir = $PSScriptRoot

# Task 1: Daily Data Sync (runs at 2 AM daily)
Write-Host "`n[1] Creating Daily Data Sync Task..." -ForegroundColor Yellow
$syncAction = New-ScheduledTaskAction -Execute "$scriptDir\scheduled_sync.bat" -WorkingDirectory $scriptDir
$syncTrigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
$syncSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$syncTask = New-ScheduledTask -Action $syncAction -Trigger $syncTrigger -Settings $syncSettings -Description "QuantSight: Syncs local player data to Cloud SQL daily"

try {
    Register-ScheduledTask -TaskName "QuantSight-CloudSync" -InputObject $syncTask -Force
    Write-Host "   SUCCESS - Data sync scheduled for 2:00 AM daily" -ForegroundColor Green
}
catch {
    Write-Host "   ERROR - Failed to create sync task: $_" -ForegroundColor Red
}

# Task 2: Endpoint Health Check (runs every 6 hours)
Write-Host "`n[2] Creating Endpoint Tests Task..." -ForegroundColor Yellow
$testAction = New-ScheduledTaskAction -Execute "$scriptDir\scheduled_tests.bat" -WorkingDirectory $scriptDir
$testTrigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
$testTrigger.Repetition = (New-ScheduledTaskTrigger -Once -At 6:00AM -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration ([TimeSpan]::MaxValue)).Repetition
$testSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$testTask = New-ScheduledTask -Action $testAction -Trigger $testTrigger -Settings $testSettings -Description "QuantSight: Tests all API endpoints every 6 hours"

try {
    Register-ScheduledTask -TaskName "QuantSight-EndpointTests" -InputObject $testTask -Force
    Write-Host "   SUCCESS - Endpoint tests scheduled every 6 hours" -ForegroundColor Green
}
catch {
    Write-Host "   ERROR - Failed to create test task: $_" -ForegroundColor Red
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host " SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "`nScheduled Tasks:" -ForegroundColor White
Write-Host "  1. QuantSight-CloudSync" -ForegroundColor Cyan
Write-Host "     Schedule: Daily at 2:00 AM" -ForegroundColor Gray
Write-Host "     Action: Sync local player data to Cloud SQL`n" -ForegroundColor Gray

Write-Host "  2. QuantSight-EndpointTests" -ForegroundColor Cyan
Write-Host "     Schedule: Every 6 hours (6am, 12pm, 6pm, 12am)" -ForegroundColor Gray
Write-Host "     Action: Test all API endpoints`n" -ForegroundColor Gray

Write-Host "Logs will be saved to: $scriptDir\logs\" -ForegroundColor Yellow

Write-Host "`nTo view tasks: " -ForegroundColor White -NoNewline
Write-Host "taskschd.msc" -ForegroundColor Cyan

Write-Host "`nTo run manually:" -ForegroundColor White
Write-Host "  Data Sync: " -NoNewline
Write-Host ".\scheduled_sync.bat" -ForegroundColor Cyan
Write-Host "  Endpoint Tests: " -NoNewline
Write-Host ".\scheduled_tests.bat" -ForegroundColor Cyan

Write-Host "`nPress any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
