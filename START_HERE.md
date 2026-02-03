# 🚀 QuantSight Cloud - Getting Started Guide

**Welcome!** This guide will help you deploy the cloud backend step by step.

---

## Where Are You Right Now?

You have successfully:

- ✅ Built the cloud backend codebase
- ✅ Created the Dockerfile
- ✅ Pushed everything to GitHub
- ✅ Created infrastructure provisioning scripts

**Next Goal**: Get the backend running (either locally for testing OR in production on Google Cloud)

---

## IMPORTANT: Choose Your Path

### Path A: Local Testing (RECOMMENDED FIRST) 🧪

**Best for**: Testing before deploying to cloud, development work, no cloud costs

**What you'll do**:

1. Install Docker Desktop (if not already installed)
2. Run the Docker test script
3. Verify the backend works locally
4. **THEN** move to cloud deployment

**Time**: 15-30 minutes  
**Cost**: $0

👉 **[Go to Path A Instructions](#path-a-local-docker-testing)**

---

### Path B: Cloud Deployment (Production) ☁️

**Best for**: After local testing works, ready to deploy to production

**What you'll do**:

1. Set up Google Cloud account (credit card required)
2. Create Cloud SQL database
3. Deploy to Cloud Run
4. Configure Firebase

**Time**: 1-2 hours  
**Cost**: ~$15-65/month

👉 **[Go to Path B Instructions](#path-b-cloud-deployment)**

---

## Path A: Local Docker Testing

### Step 1: Check if Docker is Installed

```powershell
docker --version
```

**Expected Output**: `Docker version 24.x.x`

**If you get an error**:

1. Download Docker Desktop: <https://www.docker.com/products/docker-desktop/>
2. Install it
3. Restart your computer
4. Run the command again

---

### Step 2: Build the Local Test Image

```powershell
# Navigate to the cloud build directory
cd C:\Users\georg\quantsight_engine\quantsight_cloud_build

# Run the test script
.\test_docker_build.ps1
```

**What this does**:

- Builds a Docker image with your backend code
- Starts the container locally
- Runs health checks
- Verifies `shared_core` is accessible

**Expected Output**:

```
✅ Docker image built successfully
✅ Container started
✅ Health check passed
✅ shared_core imports working
```

---

### Step 3: Test the Backend

Open your browser and go to:

```
http://localhost:8080/health
```

**Expected Response**:

```json
{
  "status": "healthy",
  "firebase_enabled": false,
  "database": "sqlite"
}
```

**If it works**: 🎉 Your backend is working! You can now move to cloud deployment.

**If it doesn't work**: Check the troubleshooting section below.

---

### Step 4: Stop the Container

```powershell
docker ps
# Note the CONTAINER ID

docker stop <CONTAINER_ID>
```

---

## Path B: Cloud Deployment

### Prerequisites Checklist

Before you start, make sure you have:

- [ ] Google Cloud account with billing enabled
- [ ] `gcloud` CLI installed ([Install Guide](https://cloud.google.com/sdk/docs/install))
- [ ] Firebase project created ([Firebase Console](https://console.firebase.google.com/))
- [ ] Local Docker testing completed (Path A)

---

### Step 1: Install Google Cloud SDK

**Windows**:

1. Download: <https://cloud.google.com/sdk/docs/install>
2. Run the installer
3. Open a new PowerShell window
4. Verify:

```powershell
gcloud --version
```

---

### Step 2: Authenticate with Google Cloud

```powershell
gcloud auth login
```

**What this does**: Opens your browser to sign in with your Google account

---

### Step 3: Set Your Project

```powershell
# List your projects
gcloud projects list

# Set the active project (replace with your actual project ID)
gcloud config set project YOUR_PROJECT_ID
```

**Example**:

```powershell
gcloud config set project quantsight-prod-12345
```

---

### Step 4: Enable Required APIs

Copy and paste this entire block:

```powershell
gcloud services enable run.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

**Time**: 2-3 minutes  
**What this does**: Activates Google Cloud services needed for deployment

---

### Step 5: Create Cloud SQL Database

This is the most important step. **Read carefully**.

```powershell
# Set variables (customize these)
$DB_INSTANCE = "quantsight-db"
$REGION = "us-central1"

# Create the database instance (this takes 5-10 minutes)
gcloud sql instances create $DB_INSTANCE `
  --database-version=POSTGRES_15 `
  --tier=db-f1-micro `
  --region=$REGION `
  --storage-size=10GB `
  --backup-start-time=03:00
```

**Cost**: ~$10-15/month for `db-f1-micro`

**Why this takes so long**: Google is provisioning a dedicated PostgreSQL server for you.

---

### Step 6: Create the Database User and Schema

```powershell
# Set a secure password
$DB_PASSWORD = "YOUR_SECURE_PASSWORD_HERE"  # Change this!

# Create application user
gcloud sql users create quantsight `
  --instance=$DB_INSTANCE `
  --password=$DB_PASSWORD

# Create the database
gcloud sql databases create nba_data --instance=$DB_INSTANCE
```

---

### Step 7: Initialize the Database Schema

```powershell
# Connect via Cloud SQL Proxy
gcloud sql connect $DB_INSTANCE --user=quantsight --database=nba_data

# When connected, you'll see a postgres prompt:
# postgres=>

# Exit for now (we'll run the schema script next)
\q
```

**Alternative method** (recommended):

```powershell
# Install Cloud SQL Proxy
# Download from: https://cloud.google.com/sql/docs/postgres/sql-proxy

# Run the proxy in a separate terminal
cloud-sql-proxy YOUR_PROJECT_ID:us-central1:quantsight-db

# In another terminal, run the schema script
cd backend\scripts
$env:DATABASE_URL = "postgresql://quantsight:YOUR_PASSWORD@localhost:5432/nba_data"
python init_cloud_db.py
```

**Expected Output**:

```
🔧 Creating database schema...
✅ Tables created:
   └─ teams
   └─ players
   └─ player_stats
   └─ player_rolling_averages
   └─ game_logs
   └─ team_defense
🎉 Database initialization complete!
```

---

### Step 8: Deploy to Cloud Run

Now for the exciting part!

```powershell
# Build and deploy in one command
gcloud run deploy quantsight-cloud `
  --source . `
  --region=us-central1 `
  --allow-unauthenticated `
  --memory=512Mi `
  --set-cloudsql-instances=YOUR_PROJECT_ID:us-central1:quantsight-db
```

**What this does**:

1. Builds the Docker image in the cloud
2. Pushes it to Google Container Registry
3. Deploys it to Cloud Run
4. Connects it to your Cloud SQL database

**Time**: 5-10 minutes

---

### Step 9: Test Your Deployment

```powershell
# Get your service URL
gcloud run services describe quantsight-cloud `
  --region=us-central1 `
  --format="value(status.url)"
```

**Copy the URL** (it will look like: `https://quantsight-cloud-xxxx-uc.a.run.app`)

Then test it:

```powershell
# Test health endpoint
curl YOUR_SERVICE_URL/health

# Test live status
curl YOUR_SERVICE_URL/live/status
```

**Expected Response**:

```json
{
  "status": "healthy",
  "firebase_enabled": true,
  "database": "postgresql",
  "producer_running": true
}
```

---

## 🎉 Success Criteria

You'll know everything worked when:

1. ✅ Health endpoint returns `200 OK`
2. ✅ Database connection works (no errors in logs)
3. ✅ Firebase is initialized (`firebase_enabled: true`)
4. ✅ Producer is running (`producer_running: true`)

---

## 🆘 Troubleshooting

### "Docker not found"

- Install Docker Desktop and restart your computer

### "gcloud not found"

- Install Google Cloud SDK and open a new PowerShell window

### "Permission denied" errors

- Run PowerShell as Administrator

### "Cloud SQL connection failed"

- Verify the instance name matches exactly
- Check that Cloud SQL API is enabled
- Ensure the service account has `cloudsql.client` role

### "Database schema creation failed"

- Check that the `DATABASE_URL` is correct
- Verify the user has CREATE TABLE permissions
- Look for detailed error messages in the output

### Build fails with "shared_core not found"

- Ensure you're building from the repository root
- Verify `shared_core/` directory exists in `quantsight_cloud_build/`

---

## 📚 What's Next After Deployment?

1. **Seed the database** with player data from desktop
2. **Set up daily team defense updates** (Cloud Scheduler)
3. **Implement Alpha Patching** (the TODO comments in the code)
4. **Connect your mobile app** to the Cloud Run URL
5. **Set up monitoring** (Cloud Logging dashboard)

---

## Quick Reference: Important Files

| File | Purpose |
|------|---------|
| `DEPLOYMENT_SETUP.md` | Full deployment commands reference |
| `Dockerfile` | Container build instructions |
| `backend/scripts/init_cloud_db.py` | Database schema creation |
| `firestore.rules` | Security rules for Firestore |
| `test_docker_build.ps1` | Local Docker testing script |

---

## Need More Help?

**Review the detailed guides**:

- Full deployment: `DEPLOYMENT_SETUP.md`
- Docker setup: `docker_containerization_guide.md`
- Architecture overview: `README.md`

**Questions to ask yourself**:

- Have I completed local testing (Path A) first?
- Do I have billing enabled on Google Cloud?
- Is Docker Desktop running?
- Did I wait for Cloud SQL instance creation to complete?
