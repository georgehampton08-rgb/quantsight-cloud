@echo off
REM Quick Deploy Script for QuantSight Cloud
REM Usage: deploy.bat

echo ===================================
echo  QUANTSIGHT QUICK DEPLOY
echo ===================================

echo Step 1: Staging changes...
git add backend/ index.html src/

echo Step 2: Committing...
git commit -m "Quick deploy update" 2>nul || echo No changes to commit

echo Step 3: Deploying to Cloud Run...
gcloud run deploy quantsight-cloud --source . --region=us-central1 --allow-unauthenticated --set-env-vars="FIREBASE_PROJECT_ID=quantsight-prod" --add-cloudsql-instances=quantsight-prod:us-central1:quantsight-db --update-secrets="DATABASE_URL=DATABASE_URL:3,GEMINI_API_KEY=GEMINI_API_KEY:latest,GITHUB_TOKEN=GITHUB_TOKEN:latest"

echo ===================================
echo  DEPLOY COMPLETE
echo ===================================
