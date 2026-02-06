# QuantSight Cloud - Automation Setup

## 🤖 Automated Tasks

This folder contains scripts for automated data sync and endpoint testing via Windows Task Scheduler.

## 📋 Quick Setup

**Run this once to set up automation:**

```powershell
.\setup_automation.ps1
```

This creates two scheduled tasks:

### 1. **Daily Data Sync** (`QuantSight-CloudSync`)

- **Schedule**: Daily at 2:00 AM
- **Action**: Syncs local player data to Cloud SQL
- **Script**: `scheduled_sync.bat`
- **Logs**: `logs/sync_YYYYMMDD.log`

### 2. **Endpoint Health Checks** (`QuantSight-EndpointTests`)

- **Schedule**: Every 6 hours (6am, 12pm, 6pm, 12am)
- **Action**: Tests all 7 API endpoints
- **Script**: `scheduled_tests.bat`
- **Logs**: `logs/test_YYYYMMDD.log`

## 🔧 Manual Testing

Run scripts manually anytime:

```bash
# Data sync
.\scheduled_sync.bat

# Endpoint tests
.\scheduled_tests.bat
```

## 📊 View Scheduled Tasks

```powershell
# Open Task Scheduler GUI
taskschd.msc

# Or list via PowerShell
Get-ScheduledTask | Where-Object {$_.TaskName -like "QuantSight*"}
```

## 📁 Logs

All logs are saved to `logs/` directory:

- `sync_YYYYMMDD.log` - Data sync results
- `test_YYYYMMDD.log` - Endpoint test results

## 🛠️ Customization

### Change Sync Schedule

Edit `setup_automation.ps1` and modify:

```powershell
$syncTrigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
```

### Change Test Frequency

Edit `setup_automation.ps1` and modify:

```powershell
-RepetitionInterval (New-TimeSpan -Hours 6)
```

## 🗑️ Uninstall

Remove scheduled tasks:

```powershell
Unregister-ScheduledTask -TaskName "QuantSight-CloudSync" -Confirm:$false
Unregister-ScheduledTask -TaskName "QuantSight-EndpointTests" -Confirm:$false
```

## 📝 What Gets Automated

### Data Sync

- Reads local SQLite database (`backend/data/nba_data.db`)
- Uploads new/changed player data to Cloud SQL
- Logs success/failure with error details

### Endpoint Tests

- Tests all 7 API endpoints
- Verifies data counts (teams, players, etc.)
- Logs pass/fail status for each endpoint

## ✅ Benefits

- **No Manual Work**: Data stays in sync automatically
- **Early Warning**: Endpoint tests catch issues immediately
- **Historical Logs**: Track sync history and test results
- **Set and Forget**: Runs even when you're not using the app

## 🔍 Troubleshooting

**Task not running?**

1. Check Task Scheduler is enabled
2. Ensure Python is in system PATH
3. Check logs for error messages

**Need to debug?**
Run scripts manually with:

```powershell
.\scheduled_sync.bat
```

Output will show in console for debugging.
