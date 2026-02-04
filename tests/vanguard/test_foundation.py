"""
Vanguard Foundation Tests
==========================
Test request ID propagation, logging, and Redis connectivity.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Import Vanguard components
from vanguard.bootstrap import vanguard_lifespan
from vanguard.middleware import RequestIDMiddleware
from vanguard.core.context import get_request_id
from vanguard.utils.request_id import generate_request_id


@pytest.fixture
async def test_app():
    """Create a minimal FastAPI app with Vanguard for testing."""
    app = FastAPI(lifespan=vanguard_lifespan)
    
    @app.get("/test")
    async def test_endpoint():
        # Get request_id from context
        request_id = get_request_id()
        return JSONResponse(
            content={"message": "test", "request_id": request_id}
        )
    
    # Add Vanguard middleware
    app.add_middleware(RequestIDMiddleware)
    
    return app


@pytest.fixture
async def client(test_app):
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_request_id_generation(client):
    """Test that middleware generates a request ID if not provided."""
    response = await client.get("/test")
    
    # Check response headers contain X-Request-ID
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] is not None
    
    # Check request_id is a valid UUID format
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 36  # UUID4 format
    assert request_id.count("-") == 4


@pytest.mark.asyncio
async def test_request_id_extraction(client):
    """Test that middleware extracts X-Request-ID from request headers."""
    custom_id = generate_request_id()
    
    response = await client.get("/test", headers={"X-Request-ID": custom_id})
    
    # Check the same ID is returned in response
    assert response.headers["X-Request-ID"] == custom_id
    
    # Check the ID is available in the endpoint via context
    body = response.json()
    assert body["request_id"] == custom_id


@pytest.mark.asyncio
async def test_request_id_in_context(client):
    """Test that request_id is accessible via ContextVar."""
    response = await client.get("/test")
    
    # Check endpoint received the request_id from context
    body = response.json()
    assert body["request_id"] is not None
    assert body["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_multiple_requests_different_ids(client):
    """Test that different requests get different request IDs."""
    response1 = await client.get("/test")
    response2 = await client.get("/test")
    
    id1 = response1.headers["X-Request-ID"]
    id2 = response2.headers["X-Request-ID"]
    
    # IDs should be unique
    assert id1 != id2
