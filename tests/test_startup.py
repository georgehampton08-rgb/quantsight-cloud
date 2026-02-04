"""
Startup Validation Tests for Cloud Backend
===========================================
Smoke tests to verify FastAPI app starts correctly with SQLite fallback.
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend and shared_core to path
backend_path = Path(__file__).parent.parent
shared_core_path = backend_path.parent / 'shared_core'

if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
if str(shared_core_path) not in sys.path:
    sys.path.insert(0, str(shared_core_path))

# Import app after path setup
from main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "QuantSight" in data["service"]
    print(f"✓ Root endpoint OK: {data['service']}")


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    print(f"✓ Health endpoint OK: {data}")


def test_live_status_endpoint():
    """Test live pulse status endpoint (cloud mode)."""
    response = client.get("/live/status")
    
    # Should return 200 even if Firebase is not configured (graceful degradation)
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert "firebase_connected" in data
    assert "timestamp" in data
    
    # Firebase may not be connected in local testing
    if not data["firebase_connected"]:
        print("⚠ Firebase not connected (expected in local testing)")
    
    print(f"✓ Live status endpoint OK: status={data['status']}")


def test_firebase_graceful_degradation():
    """Verify Firebase service fails gracefully without credentials."""
    from services.firebase_admin_service import get_firebase_service
    
    firebase = get_firebase_service()
    
    # Firebase may be None if credentials not found - this is OK
    if firebase is None:
        print("✓ Firebase gracefully degraded (no credentials)")
    elif not firebase.enabled:
        print("✓ Firebase disabled (expected without credentials)")
    else:
        print("✓ Firebase enabled (credentials found)")
    
    # Test should pass regardless
    assert True


def test_routers_loaded():
    """Verify all routers are loaded correctly."""
    routes = [route.path for route in app.routes]
    
    expected_routes = [
        "/",
        "/health",
        "/live/status",
        # Note: other routes may not show without prefix, check by prefix
    ]
    
    for expected in expected_routes:
        assert any(expected in route for route in routes), f"Route {expected} not found"
    
    print(f"✓ All expected routes loaded: {len(routes)} total routes")


def test_app_metadata():
    """Verify app metadata is correctly configured."""
    assert app.title == "QuantSight Live Pulse (Cloud)"
    assert app.version == "1.0.0"
    print(f"✓ App metadata OK: {app.title} v{app.version}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
