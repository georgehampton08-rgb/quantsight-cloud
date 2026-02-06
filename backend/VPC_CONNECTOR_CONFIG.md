# VPC Connector Configuration for NBA API Access

## Overview

The QuantSight Cloud Run service requires VPC connector access to reliably communicate with the NBA API endpoints. This document outlines the VPC configuration and verification steps.

## VPC Connector Details

- **Name**: `nba-api-connector`
- **Project**: `quantsight-prod`
- **Region**: `us-central1`
- **Purpose**: Provides stable egress IP for NBA API requests, avoiding blocks from shared Cloud Run IPs

## Cloud Run Configuration

### Service Annotations

```yaml
run.googleapis.com/vpc-access-connector: projects/quantsight-prod/locations/us-central1/connectors/nba-api-connector
run.googleapis.com/vpc-access-egress: private-ranges-only
```

### Egress Strategy

- **`private-ranges-only`**: Routes only private IP traffic through VPC connector
- **Public traffic**: Goes directly through Cloud Run's default egress (faster for CDN endpoints)

## Services Using VPC Connector

### 1. Live Pulse Service

- **File**: `backend/services/live_pulse_service_cloud.py`
- **Purpose**: Real-time game data polling every 10 seconds
- **Endpoints**: `nba_api.live.nba.endpoints.scoreboard`, `boxscore`

### 2. NBA Schedule Service

- **File**: `backend/services/nba_schedule.py`
- **Purpose**: Daily game schedule fetching
- **Endpoints**: `cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json`

### 3. NBA API Connector

- **File**: `backend/services/nba_api_connector.py`
- **Purpose**: Player stats, rosters, game logs
- **Endpoints**: `stats.nba.com/stats/*`

## Verification Steps

### 1. Check VPC Connector Exists

```bash
gcloud compute networks vpc-access connectors describe nba-api-connector \
  --region=us-central1 \
  --project=quantsight-prod
```

**Expected Output:**

```
name: nba-api-connector
network: default
ipCidrRange: 10.8.0.0/28
state: READY
```

### 2. Verify Cloud Run Service Configuration

```bash
gcloud run services describe quantsight-cloud \
  --region=us-central1 \
  --project=quantsight-prod \
  --format="value(metadata.annotations['run.googleapis.com/vpc-access-connector'])"
```

**Expected Output:**

```
projects/quantsight-prod/locations/us-central1/connectors/nba-api-connector
```

### 3. Test NBA API Access from Cloud Run

Deploy the updated service and check logs:

```bash
# Deploy
gcloud run deploy quantsight-cloud \
  --source=. \
  --region=us-central1 \
  --project=quantsight-prod

# Check logs for VPC connectivity
gcloud run services logs read quantsight-cloud \
  --region=us-central1 \
  --project=quantsight-prod \
  --limit=50 | grep -i "VPC\|pulse\|nba"
```

**Expected Log Entries:**

```
🔥 LivePulseCache v2.0.0-cloud initialized (VPC-enabled)
🚀 VPC Pulse producer started
🔄 VPC Pulse #6: 7 games, 0 live
```

### 4. Test Schedule Endpoint

```bash
curl https://quantsight-cloud-<hash>-uc.a.run.app/nba/schedule/health
```

**Expected Response:**

```json
{
  "service": "nba_schedule",
  "health": {
    "status": "healthy",
    "cache_age_seconds": 12.5,
    "cached_games_count": 7,
    "cache_ttl": 60,
    "is_cache_fresh": true
  }
}
```

## Troubleshooting

### Issue: VPC Connector Not Found

**Error:**

```
ERROR: (gcloud.run.deploy) Revision 'quantsight-cloud-00001' is not ready and cannot serve traffic.
VPC connector 'projects/quantsight-prod/locations/us-central1/connectors/nba-api-connector' not found.
```

**Solution:**

```bash
# Create VPC connector
gcloud compute networks vpc-access connectors create nba-api-connector \
  --region=us-central1 \
  --network=default \
  --range=10.8.0.0/28 \
  --project=quantsight-prod
```

### Issue: NBA API Still Blocked

**Symptoms:**

- HTTP 403 or 429 errors
- Timeouts on NBA API requests
- Empty game lists

**Diagnosis:**

```bash
# Check egress IP from Cloud Run
gcloud run services logs read quantsight-cloud \
  --region=us-central1 \
  --limit=100 | grep -i "request failed\|timeout\|403\|429"
```

**Solution:**

1. Verify VPC connector is attached: Check Cloud Run service annotations
2. Check egress setting: Should be `private-ranges-only` for NBA API
3. Test from Cloud Shell (simulates VPC environment):

   ```bash
   curl -H "User-Agent: Mozilla/5.0" \
        -H "Referer: https://www.nba.com/" \
        https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json
   ```

### Issue: Slow Response Times

**Symptoms:**

- Schedule endpoint takes >5 seconds
- Live pulse updates lag

**Diagnosis:**

```bash
# Check VPC connector throughput
gcloud compute networks vpc-access connectors describe nba-api-connector \
  --region=us-central1 \
  --format="value(minThroughput,maxThroughput)"
```

**Solution:**

```bash
# Increase VPC connector throughput (if needed)
gcloud compute networks vpc-access connectors update nba-api-connector \
  --region=us-central1 \
  --min-throughput=300 \
  --max-throughput=1000
```

## Cost Considerations

- **VPC Connector**: ~$0.05/hour (~$36/month) for min throughput
- **Egress Traffic**: ~$0.12/GB for VPC connector egress
- **Optimization**: Use `private-ranges-only` to minimize VPC traffic (CDN requests bypass VPC)

## Deployment Checklist

- [ ] VPC connector exists in `us-central1`
- [ ] Cloud Run service has VPC connector annotation
- [ ] Egress mode set to `private-ranges-only`
- [ ] Service deployed and running
- [ ] Health check endpoint returns `healthy`
- [ ] Schedule endpoint returns games
- [ ] Live pulse logs show VPC connectivity

## References

- [Cloud Run VPC Access](https://cloud.google.com/run/docs/configuring/vpc-connectors)
- [VPC Connector Pricing](https://cloud.google.com/vpc/network-pricing#vpc-access)
- [NBA API Integration Architecture](file:///C:/Users/georg/.gemini/antigravity/knowledge/sovereign_intelligence_tier/artifacts/analytical_engines/nba_integration_architecture.md)
