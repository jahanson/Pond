"""
Tests for API authentication.
"""

import pytest
from httpx import AsyncClient

from pond.api.main import app
from pond.infrastructure.database import DatabasePool


@pytest.mark.skip(reason="Endpoints not implemented yet")
@pytest.mark.asyncio
async def test_auth_required_for_api_endpoints(test_db: str):
    """Test that API endpoints require authentication."""
    # Client without API key
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # These should all return 401
        endpoints = [
            ("POST", "/api/v1/claude/store", {"content": "test"}),
            ("POST", "/api/v1/claude/search", {"query": "test"}),
            ("POST", "/api/v1/claude/recent", {"hours": 1}),
            ("POST", "/api/v1/claude/init", {}),
        ]

        for method, path, json_data in endpoints:
            response = await client.post(path, json=json_data)
            assert response.status_code == 401
            assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio
async def test_health_check_no_auth_required(test_db: str):
    """Test that health check doesn't require authentication."""
    # Initialize db_pool for the app
    app.state.db_pool = DatabasePool()
    await app.state.db_pool.initialize()

    try:
        # Client without API key
        from httpx import ASGITransport

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            assert "status" in response.json()
    finally:
        # Cleanup
        await app.state.db_pool.close()


@pytest.mark.skip(reason="Endpoints not implemented yet")
@pytest.mark.asyncio
async def test_valid_api_key_accepted(test_client, mock_ollama_response):
    """Test that valid API key is accepted."""
    # test_client fixture includes API key
    response = await test_client.post(f"/api/v1/{test_client.test_tenant}/init")
    assert response.status_code == 200


@pytest.mark.skip(reason="Endpoints not implemented yet")
@pytest.mark.asyncio
async def test_wrong_api_key_rejected(test_db: str):
    """Test that wrong API key is rejected."""
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"X-API-Key": "wrong-key"}
    ) as client:
        response = await client.post("/api/v1/claude/init")
        assert response.status_code == 401
        assert response.json() == {"error": "Unauthorized"}
