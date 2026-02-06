# Git Repository Management - QuantSight Cloud & Desktop

This guide ensures proper git commits for both repositories without cross-contamination.

---

## 📂 Repository Structure

### 1. quantsight_cloud_build (Cloud Backend)

**Location**: `c:\Users\georg\quantsight_engine\quantsight_cloud_build`

**What to Commit**:

- ✅ `backend/` - All cloud backend code
- ✅ `shared_core/` - Math libraries (copied from desktop)
- ✅ `Dockerfile`, `requirements.txt`
- ✅ `.gitignore`, `.dockerignore`
- ✅ `README.md`, deployment scripts
- ✅ `.env.cloud` (template only - without credentials)

**What to EXCLUDE** (via .gitignore):

- ❌ `venv_cloud/` - Virtual environment
- ❌ `backend/data/*.db` - SQLite databases
- ❌ `backend/.env.cloud` - Actual credentials
- ❌ `__pycache__/`, `*.pyc` - Python cache
- ❌ Firebase credentials JSON files

### 2. quantsight_dashboard_v1 (Desktop App)

**Location**: `c:\Users\georg\quantsight_engine\quantsight_dashboard_v1`

**What to Commit**:

- ✅ Desktop-specific code changes
- ✅ Frontend updates (React components)
- ✅ Desktop backend server.py changes
- ✅ Database schema updates

**What to EXCLUDE**:

- ❌ Cloud-specific files (if any wandered in)
- ❌ Build artifacts
- ❌ node_modules/, venv/

---

## 🔍 Pre-Commit Verification

### Cloud Repository Check

```powershell
cd c:\Users\georg\quantsight_engine\quantsight_cloud_build

# Check what will be committed
git status

# Verify shared_core is included (should show files)
git status shared_core/

# Verify venv_cloud is excluded (should show nothing)
git status venv_cloud/

# Check for accidentally staged desktop files
git diff --cached --name-only | Select-String -Pattern "dashboard|desktop"
```

### Desktop Repository Check

```powershell
cd c:\Users\georg\quantsight_engine\quantsight_dashboard_v1

# Check what will be committed
git status

# Verify no cloud files are staged
git diff --cached --name-only | Select-String -Pattern "cloud_build|cloud"
```

---

## 🚀 Commit & Push Commands

### Cloud Backend Repository

```powershell
cd c:\Users\georg\quantsight_engine\quantsight_cloud_build

# Stage all cloud backend files
git add .

# Verify staging (should NOT include venv_cloud, .db files, credentials)
git status

# Commit with descriptive message
git commit -m "Cloud backend scaffolding: FastAPI + Firebase + Docker

- Ported 9 mobile-facing endpoints (15% of desktop backend)
- Created Firebase Admin Service for Firestore writes
- Refactored pulse producer for cloud (removed SSE/cache)
- Added production Dockerfile with shared_core support
- Configured hybrid SQLite/PostgreSQL database
- Included deployment scripts for Cloud Run"

# Push to remote
git push origin main
```

### Desktop Application Repository

```powershell
cd c:\Users\georg\quantsight_engine\quantsight_dashboard_v1

# Stage specific changes only
git add backend/
git add quantsight_dashboard_v1/

# OR stage all if you're confident
git add .

# Verify staging (should NOT include cloud_build files)
git status

# Commit with descriptive message
git commit -m "Desktop enhancements: Player bio integration

- Integrated player bio data into PlayerProfilePage
- Added height, weight, headshot to HeroSection
- Created new API endpoints in playerApi.ts
- Maintained backward compatibility with fallbacks"

# Push to remote
git push origin master
```

---

## ⚠️ Common Issues & Fixes

### Issue 1: "venv_cloud is being tracked"

**Cause**: .gitignore was updated after venv_cloud was already staged

**Fix**:

```powershell
cd quantsight_cloud_build
git rm -r --cached venv_cloud/
git commit -m "Remove venv_cloud from tracking"
```

### Issue 2: "Credentials accidentally committed"

**Cause**: .env.cloud with real credentials was committed

**Fix**:

```powershell
# Remove from git history (DANGEROUS - only if not pushed yet)
git rm --cached backend/.env.cloud
git commit -m "Remove credentials file"

# If already pushed, must rewrite history or revoke credentials
```

### Issue 3: "shared_core not found in cloud repo"

**Cause**: shared_core was excluded in .gitignore or not copied

**Verification**:

```powershell
cd quantsight_cloud_build
ls shared_core/
# Should show: adapters/, calculators/, engines/, etc.

# If missing, re-copy from desktop
xcopy "..\quantsight_dashboard_v1\backend\shared_core" "shared_core\" /E /I /Y
git add shared_core/
```

---

## 📋 Checklist Before Push

### Cloud Repository (`quantsight_cloud_build`)

- [ ] `backend/` directory committed
- [ ] `shared_core/` directory committed (30 files)
- [ ] `Dockerfile` committed
- [ ] `requirements.txt` committed
- [ ] `.gitignore` excludes `venv_cloud/`
- [ ] `.gitignore` excludes `backend/data/*.db`
- [ ] `.gitignore` excludes `backend/.env.cloud`
- [ ] No desktop-specific files staged
- [ ] No credentials in committed files

### Desktop Repository (`quantsight_dashboard_v1`)

- [ ] Only desktop changes committed
- [ ] No cloud_build files staged
- [ ] Frontend changes verified
- [ ] Backend changes verified
- [ ] No cloud-specific config files

---

## 🎯 Quick Status Commands

```powershell
# Cloud repo - what's changed?
cd c:\Users\georg\quantsight_engine\quantsight_cloud_build
git status --short

# Desktop repo - what's changed?
cd c:\Users\georg\quantsight_engine\quantsight_dashboard_v1
git status --short

# See last commit on both repos
cd c:\Users\georg\quantsight_engine\quantsight_cloud_build
git log -1 --oneline

cd c:\Users\georg\quantsight_engine\quantsight_dashboard_v1
git log -1 --oneline
```

---

## ✅ Final Verification

After pushing, clone fresh copies to verify:

```bash
# Test cloud repo
git clone <cloud-repo-url> test_cloud_clone
cd test_cloud_clone
ls shared_core/  # Should exist
ls venv_cloud/   # Should NOT exist

# Test desktop repo
git clone <desktop-repo-url> test_desktop_clone
cd test_desktop_clone
ls backend/      # Should exist
ls cloud_build/  # Should NOT exist
```

---

## 📝 Summary

**Cloud Repo** = Backend + shared_core + Docker + deployment scripts  
**Desktop Repo** = Full desktop app + frontend + desktop backend

**Never Commit**:

- Virtual environments (venv/, venv_cloud/)
- Credentials (.env files with real secrets)
- Database files (*.db,*.sqlite)
- Build artifacts (**pycache**/, dist/)
