# QuantSight Cloud Run Deployment Script (Updated)
# Deploys API hardening fixes to production

set -e  # Exit on error

echo ""
echo "🚀 QuantSight Cloud Run Deployment"
echo "===================================="
echo ""

# Configuration
PROJECT_ID="quantsight-443700"
REGION="us-central1"
SERVICE_NAME="quantsight-cloud"
SOURCE_DIR="./backend"

echo "📋 Configuration:"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Service: $SERVICE_NAME"
echo "   Source: $SOURCE_DIR"
echo ""

# Verify we're in the right directory
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Error: backend/ directory not found"
    exit 1
fi

if [ ! -f "$SOURCE_DIR/main.py" ]; then
    echo "❌ Error: main.py not found in backend/"
    exit 1
fi

echo "✅ Source files verified"
echo ""

# Check gcloud authentication
echo "🔐 Checking authentication..."
gcloud auth list --filter=status:ACTIVE --format="value(account)" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Not authenticated. Run: gcloud auth login"
    exit 1
fi
echo "✅ Authenticated"
echo ""

# Set project
echo "🎯 Setting project..."
gcloud config set project $PROJECT_ID
echo ""

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
echo "   This will take 5-7 minutes..."
echo ""

gcloud run deploy $SERVICE_NAME \
  --source $SOURCE_DIR \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars FIREBASE_PROJECT_ID=$PROJECT_ID \
  --memory 512Mi \
  --timeout 300 \
  --max-instances 10 \
  --quiet

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment successful!"
    echo ""
    echo "🔗 Service URL:"
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format="value(status.url)")
    echo "   $SERVICE_URL"
    echo ""
    echo "📊 Next steps:"
    echo "   1. Test health: curl $SERVICE_URL/health"
    echo "   2. Run test suite: ./test_api_hardening.ps1 -BaseUrl \"$SERVICE_URL\""
    echo "   3. Monitor logs: gcloud logging tail \"resource.type=cloud_run_revision\" --limit 50"
    echo ""
else
    echo ""
    echo "❌ Deployment failed!"
    echo "   Check logs: gcloud logging read --limit 50"
    exit 1
fi
