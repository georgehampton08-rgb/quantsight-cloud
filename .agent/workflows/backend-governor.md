---
description: QuantSight Backend Governor - Sync & Separation Protocol for Desktop/Mobile
---

# QuantSight Backend Governor

This workflow enforces the source-of-truth separation rules defined in `SOURCE_OF_TRUTH_PROTOCOL.md`. Run this mentally at the start of every session that touches backend code.

## Phase 0: Identify Target

Before touching any file, determine which system you are working on:

1. **Cloud Run backend** → all edits go in `quantsight_cloud_build/backend/`
2. **Desktop dashboard** → all edits go in `quantsight_dashboard_v1/`
3. **Shared frontend (Firebase Hosting)** → edits go in `quantsight_cloud_build/src/` or `app/`

If the user says "the API", "Cloud Run", "the backend", "the server", "production", or names a specific endpoint → **Cloud Run backend (rule 1)**.

If the user says "desktop", "local", "Electron", "dashboard app" → **Desktop (rule 2)**.

## Phase 1: Pre-Edit Verification

Before editing any file:

1. Verify the file path starts with `quantsight_cloud_build/backend/` (not root-level)
   - ✅ `backend/vanguard/api/admin_routes.py`
   - ❌ `vanguard/api/admin_routes.py` (root — STALE, DO NOT EDIT)
   - ❌ `api/public_routes.py` (root — STALE, DO NOT EDIT)
   - ❌ `main.py` at root (STALE, DO NOT EDIT)

2. If you accidentally open a root-level file, close it and open the `backend/` equivalent.

// turbo
3. Confirm git is clean before starting a new feature:

```
git -C c:\Users\georg\quantsight_engine\quantsight_cloud_build status --short
```

## Phase 2: Make Edits

Edit only files within `quantsight_cloud_build/backend/`.

Key subdirectories:

- `backend/api/` — public and admin REST routes
- `backend/vanguard/` — autonomous monitoring, Inquisitor, Surgeon, Vaccine
- `backend/services/` — NBA data pipeline, pulse producer, analytics
- `backend/aegis/` — context enrichment and intelligent routing
- `backend/nexus/` — cooldown/quota management
- `backend/main.py` — FastAPI app entry point (router registration)

## Phase 3: Commit

```bash
cd c:\Users\georg\quantsight_engine\quantsight_cloud_build
git add backend/<changed-files>
git commit -m "<type>: <description>"
git push origin main
```

Never `git add` root-level stale copies (`vanguard/`, `api/`, `main.py` at root).

## Phase 4: Deploy

// turbo
Deploy from WSL to ensure consistent environment:

```
wsl -d Ubuntu --exec bash -c "cd ~/dev/quantsight_cloud_build && git fetch origin && git reset --hard origin/main && gcloud run deploy quantsight-cloud --source . --region us-central1 --project quantsight-prod --quiet > /tmp/deploy.txt 2>&1; tail -5 /tmp/deploy.txt"
```

## Phase 5: Verify

After deployment completes (exit 0), run smoke tests:

```powershell
$BASE = "https://quantsight-cloud-458498663186.us-central1.run.app"
@("/health", "/public/teams", "/vanguard/stats", "/vanguard/admin/health", "/vanguard/admin/incidents") | ForEach-Object {
    try {
        $r = Invoke-WebRequest "$BASE$_" -UseBasicParsing -TimeoutSec 20
        Write-Host "OK  $($r.StatusCode)  $_"
    } catch {
        Write-Host "ERR $($_.Exception.Response.StatusCode)  $_"
    }
}
```

## Desktop Protection Addendum

If you are asked to fix something in `quantsight_dashboard_v1/`:

1. Finish any in-progress cloud work first (commit + push)
2. Explicitly switch context: "Switching to desktop environment"
3. Desktop edits go in `quantsight_dashboard_v1/backend/`
4. Desktop does NOT use gcloud deploy — it runs via Electron locally
5. Do NOT sync desktop changes back to cloud build or vice versa
