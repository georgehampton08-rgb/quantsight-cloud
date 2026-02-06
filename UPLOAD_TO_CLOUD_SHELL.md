# Upload Backend Code to Cloud Shell

# ===================================

## The deployment is running, but from the wrong directory

You ran the deploy from `~` (home directory), not from `backend/`.

---

## Steps to Upload Your Code

### Option 1: Upload via Cloud Shell UI (Easiest)

1. **In Cloud Shell**, click the **⋮** menu (three dots) in the top-right corner
2. Select **Upload folder**
3. Browse to: `c:\Users\georg\quantsight_engine\quantsight_cloud_build\backend`
4. Upload the entire `backend` folder
5. Wait for upload to complete

Then run:

```bash
cd backend
gcloud run deploy quantsight-cloud \
  --source . \
  --region us-central1 \
  --vpc-connector vanguard-connector \
  --vpc-egress all-traffic \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars "VANGUARD_ENABLED=true,VANGUARD_MODE=SILENT_OBSERVER" \
  --set-secrets "OPENAI_API_KEY=VANGUARD_OPENAI_KEY:latest,REDIS_URL=VANGUARD_REDIS_URL:latest"
```

---

### Option 2: Create a ZIP and Upload (Alternative)

**On Windows:**

```powershell
# In PowerShell
cd c:\Users\georg\quantsight_engine\quantsight_cloud_build
Compress-Archive -Path backend -DestinationPath backend.zip
```

**In Cloud Shell:**

1. Upload `backend.zip` using **⋮** → **Upload file**
2. Unzip:

```bash
unzip backend.zip
cd backend
# Then deploy (command above)
```

---

### Option 3: Use Git (If you have a repo)

**In Cloud Shell:**

```bash
# Clone your repo
git clone https://github.com/YOUR_USERNAME/quantsight_engine.git
cd quantsight_engine/quantsight_cloud_build/backend

# Deploy
gcloud run deploy quantsight-cloud --source . --region us-central1 --vpc-connector vanguard-connector --set-secrets "OPENAI_API_KEY=VANGUARD_OPENAI_KEY:latest,REDIS_URL=VANGUARD_REDIS_URL:latest"
```

---

## What's Happening Right Now

The deployment you started is building from your **home directory**, which probably doesn't have your FastAPI app. It will likely fail because there's no `main.py` or proper app structure.

**Don't worry!** Just:

1. Wait for this current deployment to finish (or fail)
2. Upload your `backend` folder using Option 1 above
3. Run the deploy command again from the correct directory

---

## After Upload

Once your `backend` folder is uploaded, you should see:

```bash
georgehampton08@cloudshell:~ (quantsight-prod)$ ls
backend/

georgehampton08@cloudshell:~ (quantsight-prod)$ cd backend
georgehampton08@cloudshell:~/backend (quantsight-prod)$ ls
main.py  requirements.txt  vanguard/  routers/  ...
```

Then deploy from there!

---

## Quick Reference - Full Deploy Command

Once you're in the `backend` directory:

```bash
gcloud run deploy quantsight-cloud \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --vpc-connector vanguard-connector \
  --vpc-egress all-traffic \
  --set-env-vars "\
VANGUARD_ENABLED=true,\
VANGUARD_MODE=SILENT_OBSERVER,\
VANGUARD_STORAGE_PATH=/vanguard/archivist,\
VANGUARD_STORAGE_MAX_MB=500,\
VANGUARD_LLM_ENABLED=false,\
VANGUARD_SAMPLING_RATE=0.05,\
VANGUARD_VACCINE_ENABLED=false" \
  --set-secrets "\
OPENAI_API_KEY=VANGUARD_OPENAI_KEY:latest,\
REDIS_URL=VANGUARD_REDIS_URL:latest"
```

This will:

- ✅ Build your FastAPI app with Vanguard
- ✅ Connect to Redis via VPC connector
- ✅ Inject secrets (OpenAI key, Redis URL)
- ✅ Start in Silent Observer mode

---

**Next:** Upload backend folder, then run the deploy command above!
