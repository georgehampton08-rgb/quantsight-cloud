# Deployment Secrets & IAM Configuration

## QuantSight Cloud Run Deployment Guide

This document outlines the exact IAM roles, secrets, and configuration required to deploy QuantSight to Google Cloud Run.

---

## 🔐 Service Account Configuration

### Step 1: Create Service Account

```bash
# Create the service account
gcloud iam service-accounts create quantsight-backend \
    --display-name="QuantSight Backend Service Account" \
    --description="Service account for Cloud Run backend accessing Firestore and Cloud SQL"
```

### Step 2: Assign Required IAM Roles

The Cloud Run service account needs these three roles:

| Role | Purpose |
|------|---------|
| `roles/datastore.user` | Read/write access to Firestore (live_games, live_leaders) |
| `roles/cloudsql.client` | Connect to Cloud SQL PostgreSQL instance |
| `roles/secretmanager.secretAccessor` | Read Firebase credentials from Secret Manager |

```bash
# Set your project ID
PROJECT_ID="your-gcp-project-id"
SERVICE_ACCOUNT="quantsight-backend@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant Firestore access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/datastore.user"

# Grant Cloud SQL access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/cloudsql.client"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 🗄️ Secret Manager Setup

### Upload Firebase Credentials

The Firebase Admin SDK requires a service account JSON file. Store it securely in Secret Manager:

```bash
# Create the secret
gcloud secrets create firebase-credentials \
    --replication-policy="automatic"

# Upload the credentials file
gcloud secrets versions add firebase-credentials \
    --data-file="firebase_credentials.json"

# Verify the secret exists
gcloud secrets describe firebase-credentials
```

### Access the Secret in Cloud Run

When deploying, mount the secret as an environment variable or file:

```bash
# Option 1: As environment variable (recommended for small secrets)
gcloud run deploy quantsight-backend \
    --set-secrets="FIREBASE_CREDENTIALS=firebase-credentials:latest"

# Option 2: As mounted file (for larger service account files)
gcloud run deploy quantsight-backend \
    --set-secrets="/secrets/firebase/credentials.json=firebase-credentials:latest"
```

---

## 🗃️ Cloud SQL Configuration

### Create PostgreSQL Instance

```bash
# Create Cloud SQL PostgreSQL instance
gcloud sql instances create quantsight-db \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1 \
    --storage-size=10GB \
    --storage-auto-increase

# Create the database
gcloud sql databases create nba_data --instance=quantsight-db

# Create database user
gcloud sql users create quantsight_user \
    --instance=quantsight-db \
    --password="SECURE_PASSWORD_HERE"
```

### Store Database Password in Secret Manager

```bash
# Create database password secret
gcloud secrets create db-password \
    --replication-policy="automatic"

# Add the password
echo -n "SECURE_PASSWORD_HERE" | \
    gcloud secrets versions add db-password --data-file=-
```

---

## 🚀 Cloud Run Deployment

### Full Deployment Command

```bash
PROJECT_ID="your-gcp-project-id"
REGION="us-central1"
CLOUD_SQL_INSTANCE="${PROJECT_ID}:${REGION}:quantsight-db"

gcloud run deploy quantsight-backend \
    --image="gcr.io/${PROJECT_ID}/quantsight-backend:latest" \
    --platform=managed \
    --region=${REGION} \
    --allow-unauthenticated \
    --service-account="quantsight-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --add-cloudsql-instances=${CLOUD_SQL_INSTANCE} \
    --set-env-vars="CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_INSTANCE}" \
    --set-env-vars="DB_NAME=nba_data" \
    --set-env-vars="DB_USER=quantsight_user" \
    --set-secrets="DB_PASS=db-password:latest" \
    --set-secrets="FIREBASE_CREDENTIALS=firebase-credentials:latest" \
    --memory=512Mi \
    --cpu=1 \
    --timeout=300 \
    --concurrency=80
```

---

## ✅ Verification Checklist

After deployment, verify each component:

### 1. Firestore Access

```bash
curl -s https://your-cloud-run-url/health | jq '.firestore'
# Expected: { "status": "connected" }
```

### 2. Cloud SQL Access

```bash
curl -s https://your-cloud-run-url/health/data | jq '.database'
# Expected: { "status": "connected", "tables": 6 }
```

### 3. Secret Manager Access

```bash
curl -s https://your-cloud-run-url/health | jq '.secrets'
# Expected: { "firebase_credentials": "loaded" }
```

---

## 📋 Quick Reference: All Secrets

| Secret Name | Contents | Used For |
|-------------|----------|----------|
| `firebase-credentials` | Firebase Admin SDK JSON | Firestore writes |
| `db-password` | PostgreSQL password | Cloud SQL connection |

## 📋 Quick Reference: All IAM Roles

| Role | Service Account | Purpose |
|------|-----------------|---------|
| `roles/datastore.user` | quantsight-backend | Firestore read/write |
| `roles/cloudsql.client` | quantsight-backend | Cloud SQL connection |
| `roles/secretmanager.secretAccessor` | quantsight-backend | Read secrets |

---

## ⚠️ Security Notes

1. **Never commit credentials** - All secrets go in Secret Manager
2. **Use least privilege** - Only assign roles actually needed
3. **Rotate credentials** - Update Firebase credentials periodically
4. **Enable audit logs** - Monitor Cloud SQL and Firestore access

---

## 🔄 Initialize Database Schema

After first deployment, run the schema initialization job:

```bash
# Run as Cloud Run Job
gcloud run jobs create init-db \
    --image="gcr.io/${PROJECT_ID}/quantsight-backend:latest" \
    --command="python,scripts/init_cloud_db.py" \
    --set-cloudsql-instances=${CLOUD_SQL_INSTANCE} \
    --set-env-vars="DATABASE_URL=postgresql://quantsight_user@/nba_data?host=/cloudsql/${CLOUD_SQL_INSTANCE}" \
    --set-secrets="DB_PASS=db-password:latest" \
    --region=${REGION}

# Execute the job
gcloud run jobs execute init-db --region=${REGION}

# Check job status
gcloud run jobs executions list --job=init-db --region=${REGION}
```
