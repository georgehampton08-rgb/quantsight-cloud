# QuantSight Source of Truth Protocol

> **MANDATORY READ** — Any AI agent or developer working on this codebase must follow this protocol without exception.

---

## 🏛️ Authoritative Source Directories

| Target | Edit Here | Never Edit |
|---|---|---|
| **Cloud Run (backend)** | `quantsight_cloud_build/backend/` | Root-level copies (`vanguard/`, `api/`, `main.py`, etc.) |
| **Desktop Dashboard** | `quantsight_dashboard_v1/` | Anything in `quantsight_cloud_build/` |

---

## ☁️ Cloud Backend Rules

### The One Rule
>
> **ALL cloud backend edits go in `quantsight_cloud_build/backend/`**

The root of `quantsight_cloud_build/` contains stale legacy copies of `vanguard/`, `api/`, `main.py`, and other files that are **NOT deployed**. The Dockerfile is configured to `COPY backend/ .` — only the `backend/` subdirectory is packaged into the container.

### Why This Matters

Previously the Dockerfile did `COPY . .`, which deployed the root-level files. This led to a split-brain situation where edits to `backend/` were invisible to the deployed container. The Dockerfile has been corrected to `COPY backend/ .` as of Feb 24 2026.

### File Map (Cloud)

```
quantsight_cloud_build/
├── Dockerfile               ← build config only, DO NOT DEPLOY CODE HERE
├── backend/                 ← ✅ THE ONLY PLACE TO EDIT CLOUD CODE
│   ├── main.py              ← FastAPI entry point
│   ├── requirements.txt     ← Python dependencies
│   ├── api/                 ← Public & admin routes
│   ├── vanguard/            ← Autonomous monitoring system
│   ├── services/            ← Data services
│   ├── aegis/               ← Intelligent routing
│   ├── nexus/               ← NBA data pipeline
│   └── ...
├── vanguard/                ← ❌ STALE LEGACY COPY — DO NOT EDIT
├── api/                     ← ❌ STALE LEGACY COPY — DO NOT EDIT
├── main.py                  ← ❌ STALE LEGACY COPY — DO NOT EDIT
└── services/                ← ❌ STALE LEGACY COPY — DO NOT EDIT
```

### Deployment Command

Always deploy from WSL to ensure consistent git state:

```bash
# In WSL Ubuntu
cd ~/dev/quantsight_cloud_build
git pull origin main
gcloud run deploy quantsight-cloud \
  --source . \
  --region us-central1 \
  --project quantsight-prod \
  --quiet
```

Or using the PowerShell helper (runs in background):

```powershell
# In PowerShell from quantsight_cloud_build root
wsl -d Ubuntu --exec bash -c "cd ~/dev/quantsight_cloud_build && git fetch origin && git reset --hard origin/main && gcloud run deploy quantsight-cloud --source . --region us-central1 --project quantsight-prod --quiet"
```

---

## 🖥️ Desktop Dashboard Rules

### The One Rule
>
> **NEVER modify `quantsight_dashboard_v1/` when working on cloud features**

The desktop dashboard is a completely separate Electron + Python application with its own server, dependencies, and deployment lifecycle. Cloud fixes do not apply to desktop and vice versa.

### Desktop is Protected Because

- It runs locally on the developer machine (not Cloud Run)
- It uses a different server entry point (`server.py`, not `main.py`)
- It has its own SQLite database layer
- Breaking desktop blocks local development while cloud is being worked on

### If You Need to Touch Desktop

1. Finish and deploy the cloud change first
2. Explicitly call out "switching to desktop context"
3. Test locally before committing desktop changes
4. Desktop changes do NOT require a `gcloud run deploy`

---

## ✅ Quick Checklist Before Any Edit

```
[ ] Am I editing a file inside backend/ ?  → ✅ proceed
[ ] Am I editing a root-level file (vanguard/, api/, main.py)?  → ❌ STOP, open the backend/ copy
[ ] Am I editing quantsight_dashboard_v1/ for a cloud fix?  → ❌ STOP, wrong repo
[ ] Did I run: git add backend/<file> && git commit && git push?  → ✅ then deploy
```

---

## 🚨 If You Find Root-Level Files Are Out of Date

The root-level `vanguard/`, `api/`, `services/` copies can be safely ignored or deleted. They exist only as historical artifacts. If they cause confusion, they can be removed in a cleanup commit — but note that `Dockerfile`, `cloudrun-service.yaml`, `.env.cloud`, and `.git` must remain at the root.

---

*Last updated: 2026-02-24 | Enforced by: backend-governor workflow*
