# Debugging Build Failure

# =======================

## Commands to Check Build Logs

Run these in Cloud Shell to see what went wrong:

```bash
# View recent build logs
gcloud builds list --limit=5

# Get the specific build log (use the build ID from the error)
gcloud builds log a1b1d331-8fb8-4005-af2f-16fb7bd15406
```

Or click the logs URL from the error:
<https://console.cloud.google.com/cloud-build/builds;region=us-central1/a1b1d331-8fb8-4005-af2f-16fb7bd15406?project=458498663186>

---

## Common Build Failures & Fixes

### Issue 1: Missing Dockerfile or Invalid Dockerfile

**Check if Dockerfile exists:**

```bash
ls -la Dockerfile
```

If missing or incorrect, you can deploy **without** a Dockerfile:

```bash
# Remove Dockerfile temporarily
mv Dockerfile Dockerfile.bak

# Deploy using buildpacks (automatic detection)
gcloud run deploy quantsight-cloud \
  --source . \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --vpc-connector vanguard-connector \
  --vpc-egress all-traffic \
  --set-env-vars "VANGUARD_ENABLED=true,VANGUARD_MODE=SILENT_OBSERVER" \
  --set-secrets "OPENAI_API_KEY=VANGUARD_OPENAI_KEY:latest,REDIS_URL=VANGUARD_REDIS_URL:latest"
```

### Issue 2: Dependency Installation Failure

**Check requirements.txt:**

```bash
cat requirements.txt | head -20
```

**Common fixes:**

- Remove conflicting versions
- Pin specific versions that work
- Check for typos

### Issue 3: Python Version Mismatch

**Check if runtime is specified:**

```bash
cat runtime.txt 2>/dev/null || echo "No runtime.txt found"
```

**Create runtime.txt if missing:**

```bash
echo "python-3.11" > runtime.txt
```

---

## Quick Fix - Deploy Without Dockerfile

If you want to skip Dockerfile issues:

```bash
# Rename/remove Dockerfile
mv Dockerfile Dockerfile.disabled

# Create a simple Procfile for buildpacks
cat > Procfile << 'EOF'
web: uvicorn main:app --host 0.0.0.0 --port $PORT
EOF

# Deploy
gcloud run deploy quantsight-cloud \
  --source . \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --vpc-connector vanguard-connector \
  --vpc-egress all-traffic \
  --set-env-vars "VANGUARD_ENABLED=true,VANGUARD_MODE=SILENT_OBSERVER,PORT=8080" \
  --set-secrets "OPENAI_API_KEY=VANGUARD_OPENAI_KEY:latest,REDIS_URL=VANGUARD_REDIS_URL:latest"
```

---

## Next Steps

1. **Check the logs** (commands above)
2. **Identify the error** (dependency missing? Python version? Dockerfile issue?)
3. **Apply the fix**
4. **Retry deployment**

Let me know what the logs show and I'll help fix it!
