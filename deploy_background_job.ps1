# Deploy Schedule Pre-fetch Cloud Function + Cloud Scheduler

# 1. Deploy Cloud Function
Write-Host "📦 Deploying schedule pre-fetch Cloud Function..."
gcloud functions deploy prefetch-nba-schedule `
    --gen2 `
    --runtime=python311 `
    --region=us-central1 `
    --source=./cloud_functions/prefetch_schedule `
    --entry-point=prefetch_schedule `
    --trigger-http `
    --allow-unauthenticated `
    --timeout=60s `
    --memory=256MB

# 2. Create Cloud Scheduler job (runs every hour)
Write-Host "`n⏰ Creating Cloud Scheduler job..."
gcloud scheduler jobs create http schedule-prefetch-hourly `
    --location=us-central1 `
    --schedule="0 * * * *" `
    --uri="https://us-central1-quantsight-458498663186.cloudfunctions.net/prefetch-nba-schedule" `
    --http-method=GET `
    --description="Pre-fetch NBA schedule every hour to keep cache warm" `
    --max-retry-attempts=3

Write-Host "`n✅ Deployment complete!"
Write-Host "Schedule will be pre-fetched every hour at :00"
