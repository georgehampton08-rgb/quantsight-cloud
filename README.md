# QuantSight Cloud Backend

Mobile-optimized NBA analytics backend for Google Cloud Run.

## Quick Start (Local Development)

```powershell
# Run ignition script to set up environment
.\cloud_ignition.ps1

# Start server manually
cd backend
uvicorn main:app --reload
```

## Docker Build

```powershell
# Test Docker build locally
.\test_docker_build.ps1
```

## Cloud Run Deployment

```bash
# Set environment variables
export GCP_PROJECT_ID="your-project-id"
export FIREBASE_PROJECT_ID="your-firebase-project"

# Deploy to Cloud Run
chmod +x deploy_cloud_run.sh
./deploy_cloud_run.sh
```

## Architecture

- **FastAPI** web framework
- **Firebase Firestore** for real-time data
- **Cloud SQL PostgreSQL** for historical data
- **shared_core** math library (copied from desktop for parity)

## Endpoints

- `GET /` - Service info
- `GET /health` - Health check
- `GET /live/status` - Firebase connection status
- `POST /aegis/simulate/{player_id}` - Monte Carlo projections
- `GET /players/search` - Player search
- `GET /player/{id}` - Player profile
- `GET /teams` - Team list
- `GET /data/team-defense/{team}` - Team defensive ratings

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string
- `FIREBASE_PROJECT_ID` - Firebase project ID
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to Firebase service account JSON
- `PORT` - Server port (default: 8080)
- `LOG_LEVEL` - Logging level (default: INFO)
