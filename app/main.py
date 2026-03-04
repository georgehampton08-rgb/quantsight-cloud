from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app.core.config import config
from app.data.repository import FirestoreRepository, SQLiteRepository
from google.cloud import firestore

def create_app() -> FastAPI:
    app = FastAPI(title="QuantSight Cloud API", version="3.0.0")
    
    if config.environment == "production":
        db_client = firestore.Client(project=config.project_id)
        repository = FirestoreRepository(db_client)
    else:
        repository = SQLiteRepository(db_path="./data/nba_data.db")
        
    app.state.repository = repository
    app.state.config = config
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
    )
    
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "env": config.environment}
        
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
