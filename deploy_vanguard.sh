#!/bin/bash

# Vanguard Sovereign - Cloud Run Deployment Script
# =================================================
# This script deploys QuantSight backend WITH Vanguard to Cloud Run

set -e  # Exit on error

echo "🚀 Deploying QuantSight + Vanguard to Cloud Run..."

# Configuration
PROJECT_ID="quantsight-prod"
SERVICE_NAME="quantsight-cloud"
REGION="us-central1"
SOURCE_DIR="./backend"

# Step 1: Set active project
echo "📋 Setting project: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Step 2: Deploy to Cloud Run
echo "🔨 Building and deploying..."
gcloud run deploy $SERVICE_NAME \
  --source $SOURCE_DIR \
  --region $REGION \
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

echo "✅ Deployment complete!"
echo ""
echo "🔍 Verify Vanguard health:"
echo "curl https://quantsight-cloud-458498663186.us-central1.run.app/vanguard/health"
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Set up Redis (Memorystore) if not already done"
echo "2. Create secrets for OPENAI_API_KEY and REDIS_URL in Secret Manager"
echo "3. Monitor logs for 24 hours in Silent Observer mode"
echo "4. After validation, upgrade to CIRCUIT_BREAKER mode"
