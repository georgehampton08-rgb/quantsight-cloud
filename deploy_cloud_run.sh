#!/usr/bin/env bash
# QuantSight Cloud Run Deployment Script
# Deploys backend to Cloud Run (quantsight-prod project)

set -e  # Exit on error

echo ""
echo "QuantSight Cloud Run Deployment"
echo "================================"
echo ""

# Configuration
PROJECT_ID="quantsight-prod"
REGION="us-central1"
SERVICE_NAME="quantsight-cloud"
SOURCE_DIR="./backend"

echo "Configuration:"
echo "   Project:  $PROJECT_ID"
echo "   Region:   $REGION"
echo "   Service:  $SERVICE_NAME"
echo "   Source:   $SOURCE_DIR"
echo ""

# Verify we're in the right directory
if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: backend/ directory not found. Run from quantsight_cloud_build/"
    exit 1
fi

if [ ! -f "$SOURCE_DIR/main.py" ]; then
    echo "ERROR: main.py not found in backend/"
    exit 1
fi

echo "Source files verified"
echo ""

# Check gcloud authentication
echo "Checking authentication..."
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || true)
if [ -z "$ACTIVE_ACCOUNT" ]; then
    echo "ERROR: Not authenticated. Run: gcloud auth login"
    exit 1
fi
echo "Authenticated as: $ACTIVE_ACCOUNT"
echo ""

# Set project
echo "Setting project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID" --quiet
echo ""

# Pre-flight: run syntax check on critical files
echo "Pre-flight syntax check..."
SYNTAX_OK=true
for f in \
    "$SOURCE_DIR/vanguard/ai/ai_analyzer.py" \
    "$SOURCE_DIR/vanguard/api/admin_routes.py" \
    "$SOURCE_DIR/vanguard/inquisitor/middleware.py"; do
    if [ -f "$f" ]; then
        python -m py_compile "$f" 2>/dev/null || { echo "SYNTAX ERROR: $f"; SYNTAX_OK=false; }
    fi
done
if [ "$SYNTAX_OK" = false ]; then
    echo "ERROR: Syntax errors detected. Fix before deploying."
    exit 1
fi
echo "All files pass syntax check"
echo ""

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
echo "   This will take 5-7 minutes..."
echo ""

gcloud run deploy "$SERVICE_NAME" \
  --source "$SOURCE_DIR" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "FIREBASE_PROJECT_ID=$PROJECT_ID" \
  --memory 512Mi \
  --timeout 300 \
  --max-instances 10 \
  --quiet

echo ""
echo "Deployment successful!"
echo ""

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)")
echo "Service URL: $SERVICE_URL"
echo ""

# Post-deploy health check
echo "Running post-deploy health check..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 --ssl-no-revoke "$SERVICE_URL/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "Health check passed (HTTP $HTTP_CODE)"
else
    echo "WARNING: Health check returned HTTP $HTTP_CODE (may be cold-starting)"
fi
echo ""

echo "Next steps:"
echo "   1. Smoke test:  python scripts/smoke_test_vanguard.py $SERVICE_URL"
echo "   2. Monitor logs: gcloud logging tail 'resource.type=cloud_run_revision' --limit 50"
echo "   3. Check Vanguard: curl $SERVICE_URL/vanguard/admin/incidents"
echo ""
