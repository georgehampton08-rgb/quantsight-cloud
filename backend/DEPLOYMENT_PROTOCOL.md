# Desktop Protection Protocol - NBA API Fix Deployment

## ⚠️ CRITICAL: Desktop Protection Violation Occurred

During initial implementation, changes were incorrectly applied to the desktop environment (`quantsight_dashboard_v1`). This violates the Desktop Protection & Isolation (DPI) protocol.

## Corrective Actions Taken

1. ✅ Removed test file from desktop: `quantsight_dashboard_v1/backend/test_nba_schedule_service.py`
2. ⚠️ Desktop files modified (need manual review):
   - `quantsight_dashboard_v1/backend/services/nba_schedule.py`
   - `quantsight_dashboard_v1/backend/server.py`

## Proper Deployment Protocol

### Cloud Build ONLY

All NBA API fixes have been correctly applied to:

- ✅ `quantsight_cloud_build/backend/services/nba_schedule.py`
- ✅ `quantsight_cloud_build/backend/cloudrun-service.yaml` (VPC connector)

### Desktop Environment

**DO NOT MODIFY** - Desktop uses its own codebase and deployment cycle.

## Deployment Steps

```bash
# Navigate to cloud build
cd C:\Users\georg\quantsight_engine\quantsight_cloud_build\backend

# Test the service
python -m services.nba_schedule

# Deploy to Cloud Run
gcloud run deploy quantsight-cloud \
  --source=. \
  --region=us-central1 \
  --project=quantsight-prod
```

## Files Modified (Cloud Build Only)

1. **services/nba_schedule.py**
   - Added `invalidate_cache()`
   - Added `reset_session()`
   - Added `health_check()`
   - Added `force_refresh` parameter
   - Added error recovery
   - Added `reset_schedule_service()`

2. **cloudrun-service.yaml**
   - Added VPC connector annotation
   - Added egress configuration

## Verification

After deployment:

```bash
# Check health
curl https://quantsight-cloud-<hash>-uc.a.run.app/nba/schedule/health

# Test schedule
curl https://quantsight-cloud-<hash>-uc.a.run.app/schedule
```

## Lessons Learned

- ❌ Never modify `quantsight_dashboard_v1` directly
- ✅ Always work in `quantsight_cloud_build` for cloud deployments
- ✅ Desktop and Cloud are separate deployment targets
- ✅ Follow the Desktop Protection Protocol strictly
