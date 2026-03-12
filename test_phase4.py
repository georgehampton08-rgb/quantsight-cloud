import os
import sys
# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_app_factory():
    response = client.get("/health")
    assert response.status_code == 200, f"Health check failed: {response.status_code}"
    assert response.json()["status"] == "healthy", "App returned unhealthy status"
    print("Phase 4 Tests Passed.")

if __name__ == "__main__":
    test_app_factory()
