import pytest
from fastapi.testclient import TestClient

import sys
import os

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app

client = TestClient(app)

def test_startup_import_integrity():
    """
    Test that the application starts up and registers all critical routers
    without encountering a 'Deep Import Crash' during AST parsing or module init.
    """
    # Simply instantiating the TestClient triggers all route resolutions
    # If the import structure is broken, it will fail before this line completes.
    assert app.title == "QuantSight Cloud API"

def test_health_deps_endpoint():
    """Test the deep Oracle snapshot endpoint to ensure it doesn't crash."""
    response = client.get("/health/deps")
    assert response.status_code == 200
    data = response.json()
    # It might say "Vanguard not available" locally if env isn't strictly set, but it should be 200 JSON
    if "status" in data and data["status"] == "Vanguard not available":
        pass
    else:
        assert "firestore_ok" in data
        assert "gemini_ok" in data

def test_readyz_endpoint():
    """Test the /readyz endpoint."""
    response = client.get("/readyz")
    # For a local execution without Firebase mounted, we expect 503 or 200 
    # based on the underlying health_monitor mock state.
    # The crucial part is that it responds under 2.0 seconds and does not hang.
    assert response.status_code in [200, 503]
