# QuantSight Quick Fix Guide

## Issue 1: Gemini AI Insights Not Working

**Cause:** No GEMINI_API_KEY environment variable set

**Fix:**

```powershell
# Set environment variable (temporary - current session only)
$env:GEMINI_API_KEY = "your-api-key-here"

# Or set permanently (requires restart of terminal):
[System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'your-api-key-here', 'User')
```

**Get API Key:**

1. Visit: <https://makersuite.google.com/app/apikey>
2. Create/get your Gemini API key
3. Set it using one of the methods above

**After setting:**

```powershell
# Restart the backend
cd backend
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
python -m uvicorn server:app --host 127.0.0.1 --port 5000
```

## Issue 2: Other Things Not Working?

Let's diagnose what specifically isn't working:

### Test All Endpoints

```powershell
cd backend
python -c "import requests; tests = [('Schedule', 'http://localhost:5000/schedule'), ('Players', 'http://localhost:5000/players/search?q='), ('Simulate', 'http://localhost:5000/aegis/simulate/1628389?opponent_id=1610612741'), ('Matchup', 'http://localhost:5000/matchup-lab/games'), ('Injuries', 'http://localhost:5000/injuries/current')]; print('\n'.join([f'{name}: {requests.get(url, timeout=10).status_code}' for name, url in tests]))"
```

### Check Frontend

Open in browser: <http://localhost:5173>

If page doesn't load:

```powershell
# Check if Vite dev server is running
npx kill-port 5173
npm run dev
```

### Check Backend

If backend is down:

```powershell
cd backend
# Stop any existing Python processes
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Restart server
python -m uvicorn server:app --host 127.0.0.1 --port 5000
```

## Issue 3: Frontend Can't Connect to Backend

**Symptom:** Frontend loads but shows no data

**Fix:** Check CORS and verify both servers running:

```powershell
# Terminal 1 - Backend
cd backend
python -m uvicorn server:app --host 127.0.0.1 --port 5000

# Terminal 2 - Frontend  
npm run dev
```

## Quick Health Check Script

Save this as `health_check.py` in the backend folder:

```python
import requests

print("=" * 60)
print("QUANTSIGHT HEALTH CHECK")
print("=" * 60)

tests = {
    'Backend Health': 'http://localhost:5000/aegis/health',
    'Frontend': 'http://localhost:5173',
    'Schedule': 'http://localhost:5000/schedule',
    'Players Search': 'http://localhost:5000/players/search?q=',
    'Simulations': 'http://localhost:5000/aegis/simulate/1628389?opponent_id=1610612741',
    'Matchup Lab': 'http://localhost:5000/matchup-lab/games',
    'Injuries': 'http://localhost:5000/injuries/current',
}

for name, url in tests.items():
    try:
        r = requests.get(url, timeout=10)
        status = "✅" if r.status_code == 200 else f"❌ {r.status_code}"
        print(f"{status} {name}")
    except Exception as e:
        print(f"❌ {name} - {str(e)[:50]}")

print("=" * 60)
```

Run it:

```powershell
cd backend
python health_check.py
```

## Common Issues & Solutions

### "Module not found"

```powershell
cd backend
pip install -r requirements.txt
```

### "Port already in use"

```powershell
# Kill port 5000 (backend)
npx kill-port 5000

# Kill port 5173 (frontend)
npx kill-port 5173
```

### "Database locked"

```powershell
# Close any DB browser or SQL tools
# Restart backend server
```

## What Should Be Working

✅ Backend API (port 5000)
✅ Frontend UI (port 5173)  
✅ Schedule with live scores
✅ Player search (1359 players)
✅ 50k Monte Carlo simulations
✅ Matchup Lab analysis
✅ Injury reports
❌ Gemini AI insights (needs API key)

Tell me specifically what's not working and I'll help fix it!
