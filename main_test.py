"""
Minimal Cloud Run test - Just verify container starts
"""
import logging
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="QuantSight Test")

@app.get("/")
def root():
    return {"status": "ok", "service": "quantsight-test"}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
