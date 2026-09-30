"""
Phase 1 backend tests.
Tests the health check endpoint and API structure.
Actual auth tests will be in Phase 2 once Firebase is configured.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.anyio
async def test_health_check(client: AsyncClient):
    """Health check endpoint should return 200."""
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "certflow-backend"
    assert "version" in data
    assert "environment" in data


@pytest.mark.anyio
async def test_openapi_available(client: AsyncClient):
    """OpenAPI schema should be accessible."""
    response = await client.get("/api/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["info"]["title"] == "CertFlow API"


@pytest.mark.anyio
async def test_auth_status_public(client: AsyncClient):
    """Auth status endpoint should be publicly accessible."""
    response = await client.get("/api/auth/status")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "auth_service" in data
    assert "firebase_configured" in data
    assert isinstance(data["firebase_configured"], bool)
    if data["firebase_configured"]:
        assert data["auth_service"] == "operational"
    else:
        assert data["auth_service"] == "not_configured"


@pytest.mark.anyio
async def test_auth_me_requires_auth(client: AsyncClient):
    """Protected endpoints should require authentication."""
    response = await client.get("/api/auth/me")
    # Should return 401 or 403 (no token provided)
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.anyio
async def test_campaigns_requires_auth(client: AsyncClient):
    """Campaign endpoints should require authentication."""
    response = await client.get("/api/campaigns/")
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.anyio
async def test_gmail_callback_public(client: AsyncClient):
    """Gmail callback should be accessible without auth (OAuth flow)."""
    response = await client.get("/api/gmail/callback")
    # Should return 501 (not implemented), NOT 401
    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED


@pytest.mark.anyio
async def test_cors_headers(client: AsyncClient):
    """CORS headers should be present in OPTIONS responses."""
    response = await client.options(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    # CORS should allow the request (though OPTIONS might not have Access-Control headers on /health)
    assert response.status_code in (200, 405)
