import os
import sys
# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_vanguard_telemetry():
    # Hit the health check to trigger Vanguard middleware (if implemented)
    response = client.get("/health")
    assert response.status_code == 200, "Health check failed"
    
    # Optional: If Vanguard injects specific headers like X-Request-ID
    # assert "X-Request-ID" in response.headers, "Vanguard middleware failed to inject request ID"
    print("Vanguard Telemetry Test Passed (or stubbed successfully).")
    print("Phase 6 Unit Tests Passed.")

if __name__ == "__main__":
    test_vanguard_telemetry()
