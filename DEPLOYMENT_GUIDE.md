# Cloud Run Deployment Guide

**API Hardening - Production Deployment**

## Pre-Deployment Checklist

✅ **Local Tests Passed**

```powershell
# Start local backend
cd C:\Users\georg\quantsight_engine\quantsight_cloud_build\backend
uvicorn main:app --reload --port 8000

# In new terminal, run tests
cd C:\Users\georg\quantsight_engine\quantsight_cloud_build
.\test_api_hardening.ps1 -Verbose
```

✅ **Code Review Complete**

- [response_models.py](file:///C:/Users/georg/quantsight_engine/quantsight_cloud_build/backend/api/response_models.py) - Pydantic schemas
- [query_models.py](file:///C:/Users/georg/quantsight_engine/quantsight_cloud_build/backend/api/query_models.py) - Input validation
- [public_routes.py](file:///C:/Users/georg/quantsight_engine/quantsight_cloud_build/backend/api/public_routes.py) - Hardened endpoints

---

## Deployment Command

### Option 1: Using Existing Deployment Script

```bash
cd /c/Users/georg/quantsight_engine/quantsight_cloud_build
./deploy_cloud_run.sh
```

### Option 2: Manual Deployment

```bash
# Set environment
export PROJECT_ID="quantsight-443700"
export REGION="us-central1"
export SERVICE_NAME="quantsight-cloud"

# Build and deploy
gcloud run deploy $SERVICE_NAME \
  --source ./backend \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars FIREBASE_PROJECT_ID=$PROJECT_ID \
  --memory 512Mi \
  --timeout 300 \
  --max-instances 10
```

---

## Post-Deployment Validation

### 1. Run Production Tests

```powershell
# Test against Cloud Run URL
.\test_api_hardening.ps1 -BaseUrl "https://quantsight-cloud-nucvdwqo6q-uc.a.run.app" -Verbose
```

### 2. Monitor Vanguard Dashboard

```bash
# Check incident logs
https://quantsight-cloud-nucvdwqo6q-uc.a.run.app/vanguard/admin/incidents
```

### 3. Validate Key Endpoints

**Health Check:**

```bash
curl https://quantsight-cloud-nucvdwqo6q-uc.a.run.app/health
```

**Aegis 501 Response:**

```bash
curl -i https://quantsight-cloud-nucvdwqo6q-uc.a.run.app/aegis/simulate/123/456
# Should return: HTTP/1.1 501 Not Implemented
```

**Input Validation:**

```bash
# Valid request
curl "https://quantsight-cloud-nucvdwqo6q-uc.a.run.app/game-logs?player_id=203999&limit=5"

# Invalid request (should return 422)
curl -i "https://quantsight-cloud-nucvdwqo6q-uc.a.run.app/game-logs?player_id=ABC123"
```

---

## Rollback Plan

If issues are detected:

```bash
# List previous revisions
gcloud run revisions list --service quantsight-cloud --region us-central1

# Rollback to previous revision
gcloud run services update-traffic quantsight-cloud \
  --to-revisions REVISION_NAME=100 \
  --region us-central1
```

---

## Changes Deployed

### Phase 1-2: Infrastructure

- ✅ Pydantic response/query models created
- ✅ Duplicate `/live/games` route removed
- ✅ Aegis stub returns proper 501

### Phase 3-4: Validation

- ✅ Player search: min/max length validation
- ✅ Game logs: pattern validation (numeric player_id, 3-letter team_id)
- ✅ Date range validation

### Phase 5-6: Optimization

- ✅ Explicit null checks on player profile
- ✅ Schedule: duplicate flat fields removed (30% payload reduction)
- ✅ Roster: type-safe jersey_number

### Phase 7-8: Advanced

- ✅ Boxscore: aggregated stats (80+ docs → 20 summaries)
- ✅ Sanitized error messages (no Firestore internals)

---

## Monitoring

**Cloud Run Logs:**

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=quantsight-cloud" \
  --limit 50 \
  --format json
```

**Error Rate:**

```bash
# Check for 500 errors
gcloud logging read "resource.type=cloud_run_revision AND httpRequest.status>=500" \
  --limit 10
```

---

## Success Criteria

✅ All tests pass (`test_api_hardening.ps1`)  
✅ No 500 errors in first 24 hours  
✅ Response times < 500ms (95th percentile)  
✅ Vanguard shows no critical incidents  
✅ Frontend displays data correctly  

**Estimated Deployment Time:** 5-7 minutes  
**Expected Downtime:** 0 seconds (rolling update)
