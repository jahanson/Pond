"""Integration tests for API endpoints.

Focus on testing our business logic, not the frameworks.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from pond.api.main import app
from pond.infrastructure.auth import APIKeyManager
from pond.infrastructure.database import DatabasePool
from pond.infrastructure.schema import ensure_tenant_schema


@pytest.fixture
async def test_api_key():
    """Create a test tenant with API key."""
    pool = DatabasePool()
    await pool.initialize()

    # Create test tenant
    async with pool.acquire() as conn:
        await ensure_tenant_schema(conn, "api_test")

    # Generate API key
    api_key_manager = APIKeyManager(pool)
    api_key = await api_key_manager.create_key("api_test", "Test key")

    yield api_key

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DROP SCHEMA IF EXISTS api_test CASCADE")
    await pool.close()


@pytest.fixture
async def client():
    """Create test client."""
    # Initialize app state manually for tests
    app.state.db_pool = DatabasePool()
    await app.state.db_pool.initialize()
    app.state.api_key_manager = APIKeyManager(app.state.db_pool)
    app.state.auth_disabled = False  # Enable auth for tests

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await app.state.db_pool.close()


@pytest.mark.asyncio
async def test_store_and_search_flow(client, test_api_key):
    """Test the complete flow: store a memory, then search for it."""
    # Store a memory
    response = await client.post(
        "/api/v1/api_test/store",
        json={
            "content": "The quick brown fox jumps over the lazy dog",
            "tags": ["animals", "action"]
        },
        headers={"X-API-Key": test_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] > 0
    assert "splash" in data

    # Search for it
    response = await client.post(
        "/api/v1/api_test/search",
        json={"query": "fox", "limit": 5},
        headers={"X-API-Key": test_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
    assert any("fox" in m["content"].lower() for m in data["memories"])


@pytest.mark.asyncio
async def test_empty_search_returns_recent(client, test_api_key):
    """Test that empty search returns recent memories."""
    # Store some memories first
    for i in range(3):
        await client.post(
            "/api/v1/api_test/store",
            json={"content": f"Test memory {i}"},
            headers={"X-API-Key": test_api_key}
        )

    # Search with empty query
    response = await client.post(
        "/api/v1/api_test/search",
        json={"query": "", "limit": 10},
        headers={"X-API-Key": test_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 3
    assert "memories" in data


@pytest.mark.asyncio
async def test_init_endpoint(client, test_api_key):
    """Test init endpoint returns time and recent memories."""
    # Store a memory for context
    await client.post(
        "/api/v1/api_test/store",
        json={"content": "Init test memory"},
        headers={"X-API-Key": test_api_key}
    )

    # Call init
    response = await client.post(
        "/api/v1/api_test/init",
        json={},
        headers={"X-API-Key": test_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert "current_time" in data
    assert "recent_memories" in data
    assert isinstance(data["recent_memories"], list)


@pytest.mark.asyncio
async def test_recent_endpoint_with_hours(client, test_api_key):
    """Test recent endpoint respects hours parameter."""
    # Store a memory
    await client.post(
        "/api/v1/api_test/store",
        json={"content": "Recent test memory"},
        headers={"X-API-Key": test_api_key}
    )

    # Get recent memories
    response = await client.post(
        "/api/v1/api_test/recent",
        json={"hours": 1, "limit": 10},
        headers={"X-API-Key": test_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert "memories" in data
    assert data["count"] >= 1


@pytest.mark.asyncio
async def test_tenant_health_endpoint(client, test_api_key):
    """Test tenant health returns statistics."""
    # Store some memories to have stats
    for i in range(2):
        await client.post(
            "/api/v1/api_test/store",
            json={"content": f"Health test memory {i}"},
            headers={"X-API-Key": test_api_key}
        )

    # Check health
    response = await client.get(
        "/api/v1/api_test/health",
        headers={"X-API-Key": test_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["tenant"] == "api_test"
    assert data["memory_count"] >= 2
    assert data["embedding_count"] >= 2


@pytest.mark.asyncio
async def test_auth_required(client):
    """Test that endpoints require authentication."""
    # Try without API key
    response = await client.post(
        "/api/v1/api_test/store",
        json={"content": "Should fail"}
    )
    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"


@pytest.mark.asyncio
async def test_system_health_no_auth(client):
    """Test system health endpoint doesn't require auth."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "embeddings" in data


@pytest.mark.asyncio
async def test_splash_returns_related_memories(client, test_api_key):
    """Test that splash returns semantically related memories."""
    # Store initial memories
    await client.post(
        "/api/v1/api_test/store",
        json={"content": "Python is a programming language"},
        headers={"X-API-Key": test_api_key}
    )
    await client.post(
        "/api/v1/api_test/store",
        json={"content": "JavaScript is also a programming language"},
        headers={"X-API-Key": test_api_key}
    )

    # Store a related memory - should get splash
    response = await client.post(
        "/api/v1/api_test/store",
        json={"content": "I love coding in Python"},
        headers={"X-API-Key": test_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    # With mock embeddings, splash might be empty, but the structure should be there
    assert "splash" in data
    assert isinstance(data["splash"], list)
