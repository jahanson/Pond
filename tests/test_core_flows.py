"""Test core Pond flows with full mocking - no database required!"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from pond.api.main import app
from pond.domain.memory import Memory


@pytest.fixture
async def mock_app():
    """Create app with all dependencies mocked."""
    # Mock the dependencies
    mock_db_pool = MagicMock()
    mock_api_manager = MagicMock()
    mock_repository = AsyncMock()

    # Set up app state
    app.state.db_pool = mock_db_pool
    app.state.api_key_manager = mock_api_manager
    app.state.memory_repository = mock_repository

    # Mock auth to always succeed for "test-key"
    async def mock_validate(api_key):
        if api_key == "test-key":
            return "test_tenant"
        raise ValueError("Invalid API key")

    mock_api_manager.validate_key = AsyncMock(side_effect=mock_validate)

    return app, mock_repository


@pytest.fixture
async def client(mock_app):
    """Create test client with mocked app."""
    app, _ = mock_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_store_memory_success(client, mock_app):
    """Test successful memory storage."""
    _, mock_repo = mock_app

    # Mock the store method to return a Memory object and empty splash
    stored_memory = Memory(
        id=42,
        content="I learned about quantum computing today!",
        metadata={
            "created_at": datetime.now(UTC).isoformat(),
            "tags": ["quantum", "learning"],
            "entities": [],
            "actions": []
        }
    )
    mock_repo.store.return_value = (stored_memory, [])

    response = await client.post(
        "/api/v1/store",
        json={
            "content": "I learned about quantum computing today!",
            "tags": ["quantum", "learning"]
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["splash"] == []

    # Verify the repository was called correctly
    mock_repo.store.assert_called_once()
    call_args = mock_repo.store.call_args
    assert call_args[1]["tenant"] == "test_tenant"
    assert "quantum computing" in call_args[1]["content"]


@pytest.mark.asyncio
async def test_store_memory_with_splash(client, mock_app):
    """Test memory storage returns related memories in splash."""
    _, mock_repo = mock_app

    # Mock stored memory and splash memories
    stored_memory = Memory(
        id=43,
        content="More quantum stuff!",
        metadata={
            "created_at": datetime.now(UTC).isoformat(),
            "tags": [],
            "entities": [],
            "actions": []
        }
    )

    splash_memories = [
        Memory(
            id=10,
            content="Quantum entanglement is spooky action at a distance",
            metadata={
                "created_at": datetime.now(UTC).isoformat(),
                "tags": ["quantum", "physics"],
                "entities": [],
                "actions": []
            }
        )
    ]

    mock_repo.store.return_value = (stored_memory, splash_memories)

    response = await client.post(
        "/api/v1/store",
        json={"content": "More quantum stuff!"},
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["splash"]) == 1
    assert "spooky action" in data["splash"][0]["content"]


@pytest.mark.asyncio
async def test_search_memories(client, mock_app):
    """Test semantic search."""
    _, mock_repo = mock_app

    # Mock search results
    mock_memories = [
        Memory(
            id=1,
            content="Python is a great programming language",
            metadata={
                "created_at": datetime.now(UTC).isoformat(),
                "tags": ["python", "programming"],
                "entities": [],
                "actions": ["program"]
            }
        )
    ]

    mock_repo.search.return_value = mock_memories

    response = await client.post(
        "/api/v1/search",
        json={"query": "coding in python", "limit": 5},
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    results = response.json()
    assert "memories" in results
    assert results["count"] == 1
    assert "Python" in results["memories"][0]["content"]


@pytest.mark.asyncio
async def test_recent_memories(client, mock_app):
    """Test retrieving recent memories."""
    _, mock_repo = mock_app

    mock_memories = [
        Memory(
            id=1,
            content="Recent memory 1",
            metadata={
                "created_at": datetime.now(UTC).isoformat(),
                "tags": [],
                "entities": [],
                "actions": []
            }
        ),
        Memory(
            id=2,
            content="Recent memory 2",
            metadata={
                "created_at": datetime.now(UTC).isoformat(),
                "tags": [],
                "entities": [],
                "actions": []
            }
        )
    ]

    mock_repo.get_recent.return_value = mock_memories

    response = await client.post(
        "/api/v1/recent",
        json={"hours": 24, "limit": 10},
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["memories"]) == 2
    assert data["memories"][0]["id"] == 1


@pytest.mark.asyncio
async def test_init_endpoint(client, mock_app):
    """Test initialization endpoint."""
    _, mock_repo = mock_app

    # Mock recent memories for init
    mock_memories = [
        Memory(
            id=99,
            content="System initialized",
            metadata={
                "created_at": datetime.now(UTC).isoformat(),
                "tags": ["init"],
                "entities": [],
                "actions": []
            }
        )
    ]

    mock_repo.get_recent.return_value = mock_memories

    response = await client.post(
        "/api/v1/init",
        json={},
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()

    # Check current time is reasonable
    assert "current_time" in data
    current_time = datetime.fromisoformat(data["current_time"].replace("Z", "+00:00"))
    now = datetime.now(UTC)
    assert abs((now - current_time).total_seconds()) < 5

    # Check recent memories
    assert "recent_memories" in data
    assert len(data["recent_memories"]) == 1
    assert data["recent_memories"][0]["content"] == "System initialized"


@pytest.mark.asyncio
async def test_auth_missing_key(client, mock_app):
    """Test that missing API key returns 401."""
    response = await client.post(
        "/api/v1/store",
        json={"content": "Should fail"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_invalid_key(client, mock_app):
    """Test that invalid API key returns 401."""
    response = await client.post(
        "/api/v1/store",
        json={"content": "Should also fail"},
        headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_validation_empty_content(client, mock_app):
    """Test that empty content is rejected."""
    response = await client.post(
        "/api/v1/store",
        json={"content": ""},
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_validation_content_too_long(client, mock_app):
    """Test that overly long content is rejected."""
    long_content = "x" * 10001  # Over our limit
    response = await client.post(
        "/api/v1/store",
        json={"content": long_content},
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 422  # FastAPI validation error
