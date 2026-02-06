#!/bin/bash
# QuantSight Cloud Backend - Cloud Run Deployment Script
# ========================================================
# Production deployment to Google Cloud Run

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="quantsight-cloud"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Cloud SQL Connection (update with your instance)
CLOUD_SQL_INSTANCE="${PROJECT_ID}:${REGION}:nba-database"

# Firestore Project
FIREBASE_PROJECT_ID="${FIREBASE_PROJECT_ID:-${PROJECT_ID}}"

echo "========================================="
echo "QuantSight Cloud Run Deployment"
echo "========================================="
echo ""
echo "Project ID: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Step 1: Build and push Docker image to Google Container Registry
echo "[1/3] Building and pushing Docker image..."
echo ""

gcloud builds submit \
    --tag ${IMAGE_NAME} \
    --project ${PROJECT_ID} \
    .

if [ $? -ne 0 ]; then
    echo "ERROR: Docker build failed"
    exit 1
fi

echo ""
echo "✓ Image pushed to ${IMAGE_NAME}"
echo ""

# Step 2: Deploy to Cloud Run
echo "[2/3] Deploying to Cloud Run..."
echo ""

gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --timeout 300 \
    --set-env-vars "FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID},LOG_LEVEL=INFO" \
    --set-env-vars "DATABASE_URL=postgresql://user:password@/cloudsql/${CLOUD_SQL_INSTANCE}/nba_data" \
    --add-cloudsql-instances ${CLOUD_SQL_INSTANCE} \
    --service-account ${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com

if [ $? -ne 0 ]; then
    echo "ERROR: Cloud Run deployment failed"
    exit 1
fi

echo ""
echo "✓ Deployment successful"
echo ""

# Step 3: Get service URL
echo "[3/3] Retrieving service URL..."
echo ""

SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)')

echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Service URL: ${SERVICE_URL}"
echo "Health Check: ${SERVICE_URL}/health"
echo "Live Status: ${SERVICE_URL}/live/status"
echo ""
echo "To view logs:"
echo "  gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}\" --limit 50 --project ${PROJECT_ID}"
echo ""
echo "To update environment variables:"
echo "  gcloud run services update ${SERVICE_NAME} --set-env-vars KEY=VALUE --region ${REGION} --project ${PROJECT_ID}"
echo ""

# Test the deployment
echo "Testing deployment..."
curl -s ${SERVICE_URL}/health | python -m json.tool

echo ""
echo "========================================="
