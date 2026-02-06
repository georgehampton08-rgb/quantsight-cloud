# QuantSight Cloud Deployment Setup Guide

**Date**: 2026-02-02  
**Target**: Google Cloud Platform (Cloud Run + Cloud SQL + Firestore)

---

## Prerequisites

- Google Cloud SDK installed (`gcloud`)
- Active GCP billing account
- Firebase project linked to GCP project

---

## Phase 1: Project Setup

### 1.1 Set Environment Variables

```bash
# Replace with your actual values
export PROJECT_ID="quantsight-prod"
export REGION="us-central1"
export SERVICE_NAME="quantsight-cloud"
export DB_INSTANCE="quantsight-db"
export DB_NAME="nba_data"
export DB_USER="quantsight"
```

### 1.2 Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  cloudbuild.googleapis.com \
  --project=$PROJECT_ID
```

---

## Phase 2: Cloud SQL PostgreSQL Instance

### 2.1 Create Cloud SQL Instance (Start Small)

```bash
# Create Postgres 15 instance (db-f1-micro for dev, db-g1-small for prod)
gcloud sql instances create $DB_INSTANCE \
  --project=$PROJECT_ID \
  --region=$REGION \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --storage-size=10GB \
  --storage-type=SSD \
  --availability-type=ZONAL \
  --backup-start-time=03:00 \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=04
```

### 2.2 Set Root Password

```bash
gcloud sql users set-password postgres \
  --instance=$DB_INSTANCE \
  --project=$PROJECT_ID \
  --password="YOUR_SECURE_PASSWORD_HERE"
```

### 2.3 Create Application User

```bash
gcloud sql users create $DB_USER \
  --instance=$DB_INSTANCE \
  --project=$PROJECT_ID \
  --password="APP_USER_PASSWORD_HERE"
```

### 2.4 Create Database

```bash
gcloud sql databases create $DB_NAME \
  --instance=$DB_INSTANCE \
  --project=$PROJECT_ID
```

### 2.5 Get Connection Name

```bash
# Save this for Cloud Run configuration
gcloud sql instances describe $DB_INSTANCE \
  --project=$PROJECT_ID \
  --format="value(connectionName)"
  
# Output: quantsight-prod:us-central1:quantsight-db
```

---

## Phase 3: Service Account Setup

### 3.1 Create Cloud Run Service Account

```bash
gcloud iam service-accounts create quantsight-runner \
  --project=$PROJECT_ID \
  --display-name="QuantSight Cloud Run Service"
```

### 3.2 Grant Required Roles

```bash
# Cloud SQL Client (connect to database)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:quantsight-runner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

# Firestore User (read/write to Firestore)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:quantsight-runner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

# Secret Manager Accessor (read secrets)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:quantsight-runner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Logging Writer (send logs to Cloud Logging)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:quantsight-runner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"
```

---

## Phase 4: Secrets Management

### 4.1 Upload Firebase Credentials

```bash
# Create secret for Firebase service account key
gcloud secrets create firebase-credentials \
  --project=$PROJECT_ID \
  --replication-policy="automatic"

# Upload the JSON key file
gcloud secrets versions add firebase-credentials \
  --project=$PROJECT_ID \
  --data-file="path/to/firebase_credentials.json"
```

### 4.2 Create Database Password Secret

```bash
gcloud secrets create db-password \
  --project=$PROJECT_ID \
  --replication-policy="automatic"

echo -n "APP_USER_PASSWORD_HERE" | gcloud secrets versions add db-password \
  --project=$PROJECT_ID \
  --data-file=-
```

---

## Phase 5: Firestore Setup

### 5.1 Deploy Security Rules

```bash
# From quantsight_cloud_build directory
firebase deploy --only firestore:rules --project=$PROJECT_ID
```

### 5.2 Create Firestore Indexes (optional)

```bash
# If you have firestore.indexes.json
firebase deploy --only firestore:indexes --project=$PROJECT_ID
```

---

## Phase 6: Cloud Run Deployment

### 6.1 Build and Push Docker Image

```bash
# Build from repository root (captures shared_core)
cd quantsight_cloud_build

gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --project=$PROJECT_ID \
  .
```

### 6.2 Deploy to Cloud Run

```bash
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --project=$PROJECT_ID \
  --region=$REGION \
  --platform managed \
  --allow-unauthenticated \
  --service-account=quantsight-runner@${PROJECT_ID}.iam.gserviceaccount.com \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=300 \
  --set-env-vars="FIREBASE_PROJECT_ID=${PROJECT_ID},LOG_LEVEL=INFO" \
  --set-secrets="DB_PASSWORD=db-password:latest" \
  --add-cloudsql-instances="${PROJECT_ID}:${REGION}:${DB_INSTANCE}" \
  --set-env-vars="DATABASE_URL=postgresql://${DB_USER}:\${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${PROJECT_ID}:${REGION}:${DB_INSTANCE}"
```

---

## Phase 7: Database Schema Initialization

### 7.1 Run Schema Script

```bash
# Connect via Cloud SQL Proxy first
./cloud-sql-proxy "${PROJECT_ID}:${REGION}:${DB_INSTANCE}" &

# Set connection string
export DATABASE_URL="postgresql://${DB_USER}:APP_USER_PASSWORD@localhost:5432/${DB_NAME}"

# Run initialization
cd backend/scripts
python init_cloud_db.py
```

---

## Phase 8: Verification

### 8.1 Test Health Endpoint

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(status.url)")

# Test health
curl $SERVICE_URL/health
```

### 8.2 Test Firebase Connection

```bash
curl $SERVICE_URL/live/status
```

### 8.3 View Logs

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
  --project=$PROJECT_ID \
  --limit=50
```

---

## Cost Estimation (Monthly)

| Resource | Tier | Estimated Cost |
|----------|------|----------------|
| Cloud SQL (db-f1-micro) | 1 vCPU, 614MB RAM | $10-15 |
| Cloud Run | 512MB, min=0 | $0-50 (pay per use) |
| Firestore | Spark (free tier) | $0 |
| Secret Manager | 3 secrets | $0.03 |
| Cloud Build | 120 min/day free | $0 |

**Total Estimated**: $15-65/month (scales with traffic)

---

## Security Checklist

- [ ] Firebase credentials stored in Secret Manager (not environment variable)
- [ ] Service account has minimal required permissions
- [ ] Cloud SQL not exposed to public internet
- [ ] Firestore rules deployed with Alpha Protection
- [ ] `player_rolling_averages` table NOT in Firestore
- [ ] All passwords are strong and unique

---

## Troubleshooting

### Database Connection Failed

```bash
# Verify Cloud SQL instance is running
gcloud sql instances describe $DB_INSTANCE --project=$PROJECT_ID

# Check service account has cloudsql.client role
gcloud projects get-iam-policy $PROJECT_ID \
  --format="json" | jq '.bindings[] | select(.role=="roles/cloudsql.client")'
```

### Firebase Writes Failing

```bash
# Check Firestore rules
firebase firestore:get /live_games/test --project=$PROJECT_ID

# Verify service account has datastore.user role
gcloud projects get-iam-policy $PROJECT_ID \
  --format="json" | jq '.bindings[] | select(.role=="roles/datastore.user")'
```

### Container Won't Start

```bash
# Check build logs
gcloud builds list --project=$PROJECT_ID --limit=5

# Check runtime logs
gcloud logging read "resource.type=cloud_run_revision" \
  --project=$PROJECT_ID --limit=20
```

---

## Next Steps After Deployment

1. **Initialize Database Schema**: Run `init_cloud_db.py`
2. **Seed Player Data**: Import players from desktop SQLite
3. **Configure Daily Team Defense Update**: Set up Cloud Scheduler
4. **Connect Mobile App**: Update API base URL to Cloud Run service
5. **Monitor Performance**: Set up Cloud Monitoring dashboard
