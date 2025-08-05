"""
Critical path tests for Pond's core functionality.
"""

import asyncpg
import pytest
from httpx import AsyncClient

from pond.config import settings


@pytest.mark.asyncio
async def test_store_memory_with_splash(test_client, mock_ollama_response):
    """Test that storing a memory returns relevant splash memories."""
    # Store first memory about Sparkle
    response1 = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={
            "content": "Sparkle stole pizza from the counter",
            "tags": ["sparkle", "theft", "pizza"],
        },
    )
    assert response1.status_code == 200
    data1 = response1.json()

    # Verify response structure matches spec
    assert "id" in data1
    assert "content" in data1
    assert "tags" in data1
    assert "entities" in data1
    assert "actions" in data1
    assert "created_at" in data1
    assert "splash" in data1

    assert data1["splash"] == []  # First memory has no splash

    # Store second memory about Sparkle
    response2 = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={
            "content": "Sparkle stole bacon this morning",
            "tags": ["sparkle", "theft", "bacon"],
        },
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Should get splash with the pizza memory
    assert len(data2["splash"]) > 0
    assert "pizza" in data2["splash"][0]["content"]
    assert data2["splash"][0]["similarity"] > 0.7


@pytest.mark.asyncio
async def test_tenant_isolation(test_db, mock_ollama_response):
    """Test that memories are isolated between tenants."""
    # This test needs special handling to test actual multi-tenancy
    # We'll create two separate tenant schemas and verify isolation

    # Create connections for setup
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=test_db,
    )

    try:
        # Set up Claude's schema
        await conn.execute('CREATE SCHEMA IF NOT EXISTS "claude"')
        await conn.execute('SET search_path TO "claude"')
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                tags JSONB DEFAULT '[]',
                entities JSONB DEFAULT '[]',
                actions JSONB DEFAULT '[]',
                embedding public.vector(768),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                active BOOLEAN DEFAULT true
            )
        """)

        # Set up Alpha's schema
        await conn.execute('CREATE SCHEMA IF NOT EXISTS "alpha"')
        await conn.execute('SET search_path TO "alpha"')
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                tags JSONB DEFAULT '[]',
                entities JSONB DEFAULT '[]',
                actions JSONB DEFAULT '[]',
                embedding public.vector(768),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                active BOOLEAN DEFAULT true
            )
        """)

        # Now test with the API
        async with AsyncClient(
            base_url=f"http://test:{settings.port}",
            headers={"X-API-Key": "test-key"},
        ) as client:
            # Store memory for Claude
            await client.post(
                "/api/v1/claude/store",
                json={
                    "content": "Claude's private thought about Python",
                    "tags": ["python", "private"],
                },
            )

            # Store memory for Alpha
            await client.post(
                "/api/v1/alpha/store",
                json={
                    "content": "Alpha's private thought about JavaScript",
                    "tags": ["javascript", "private"],
                },
            )

            # Search Claude's memories
            claude_response = await client.post(
                "/api/v1/claude/search", json={"query": "private thought", "limit": 10}
            )
            claude_data = claude_response.json()
            assert "memories" in claude_data
            claude_memories = claude_data["memories"]

            # Claude should only see their own memory
            assert len(claude_memories) == 1
            assert "Python" in claude_memories[0]["content"]
            assert "JavaScript" not in claude_memories[0]["content"]

            # Search Alpha's memories
            alpha_response = await client.post(
                "/api/v1/alpha/search", json={"query": "private thought", "limit": 10}
            )
            alpha_data = alpha_response.json()
            assert "memories" in alpha_data
            alpha_memories = alpha_data["memories"]

            # Alpha should only see their own memory
            assert len(alpha_memories) == 1
            assert "JavaScript" in alpha_memories[0]["content"]
            assert "Python" not in alpha_memories[0]["content"]

    finally:
        # Clean up
        await conn.execute('DROP SCHEMA IF EXISTS "claude" CASCADE')
        await conn.execute('DROP SCHEMA IF EXISTS "alpha" CASCADE')
        await conn.close()


@pytest.mark.asyncio
async def test_memory_init_returns_recent_and_context(
    test_client, mock_ollama_response
):
    """Test that init returns personality context and recent memories."""
    # Store some memories first
    memories = [
        "User prefers uv over pip for Python",
        "Sparkle is a criminal mastermind cat",
        "We debugged a semicolon for 2 hours",
    ]

    for memory in memories:
        await test_client.post(
            f"/api/v1/{test_client.test_tenant}/store", json={"content": memory}
        )

    # Call init
    response = await test_client.post(f"/api/v1/{test_client.test_tenant}/init")
    assert response.status_code == 200

    data = response.json()
    assert "current_time" in data
    assert "recent_memories" in data

    # Check timestamp format
    from datetime import datetime

    datetime.fromisoformat(data["current_time"].replace("Z", "+00:00"))

    # Should have our recent memories
    assert len(data["recent_memories"]) > 0
    # Recent memories should be full memory objects
    for memory in data["recent_memories"]:
        assert "id" in memory
        assert "content" in memory
        assert "created_at" in memory
        assert "tags" in memory
        assert "entities" in memory
        assert "actions" in memory

    # Most recent memories should include what we just stored
    recent_contents = " ".join(m["content"] for m in data["recent_memories"])
    assert "Sparkle" in recent_contents or "semicolon" in recent_contents


@pytest.mark.asyncio
async def test_search_by_semantic_similarity(test_client, mock_ollama_response):
    """Test semantic search finds related memories."""
    # Store memories about different topics
    await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Sparkle the cat stole pizza again"},
    )
    await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Python debugging is frustrating"},
    )
    await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "My cat Sparkle's criminal activities continue"},
    )

    # Search for cat-related memories
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/search",
        json={"query": "feline mischief", "limit": 10},
    )

    data = response.json()
    assert "memories" in data
    memories = data["memories"]

    # Check memory structure
    for memory in memories:
        assert "id" in memory
        assert "content" in memory
        assert "created_at" in memory
        assert "tags" in memory
        assert "entities" in memory
        assert "actions" in memory
        assert "similarity" in memory

    # Should find Sparkle memories but not Python
    sparkle_count = sum(1 for m in memories if "Sparkle" in m["content"])
    python_count = sum(1 for m in memories if "Python" in m["content"])

    assert sparkle_count >= 2
    assert python_count == 0


@pytest.mark.asyncio
async def test_get_recent_memories(test_client, mock_ollama_response):
    """Test retrieving recent memories within time window."""
    # Store a memory
    await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Just stored this memory"},
    )

    # Get recent memories
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/recent", json={"hours": 1, "limit": 10}
    )

    assert response.status_code == 200
    data = response.json()
    assert "memories" in data
    memories = data["memories"]
    assert len(memories) > 0

    # Check memory structure
    for memory in memories:
        assert "id" in memory
        assert "content" in memory
        assert "created_at" in memory
        assert "tags" in memory
        assert "entities" in memory
        assert "actions" in memory

    assert "Just stored this memory" in memories[0]["content"]


@pytest.mark.asyncio
async def test_splash_similarity_threshold(test_client, mock_ollama_response):
    """Test that splash only returns memories within similarity range."""
    # This test would need different embeddings to test properly
    # For now, we'll test the structure

    # Store multiple memories
    for i in range(5):
        await test_client.post(
            f"/api/v1/{test_client.test_tenant}/store",
            json={"content": f"Memory number {i}"},
        )

    # Store one more and check splash
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store", json={"content": "Final memory"}
    )

    splash = response.json()["splash"]
    # Should have at most 3 memories (as defined in our design)
    assert len(splash) <= 3

    # Each should have similarity score
    for memory in splash:
        assert "content" in memory
        assert "similarity" in memory
        assert 0 <= memory["similarity"] <= 1


@pytest.mark.asyncio
async def test_auto_tagging_and_entity_extraction(test_client, mock_ollama_response):
    """Test that memories are auto-tagged and entities are extracted."""
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={
            "content": "Sparkle the cat loves stealing pizza from the counter",
            "tags": ["manual-tag"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Check auto-generated tags (should include entity names, nouns)
    assert "tags" in data
    assert "manual-tag" in data["tags"]  # User tag preserved
    # Should have auto-tags from entities and noun chunks
    assert any(tag in ["sparkle", "cat", "pizza", "counter"] for tag in data["tags"])

    # Check entity extraction
    assert "entities" in data
    entities = data["entities"]
    assert len(entities) > 0
    # Should find "Sparkle" as an entity
    assert any(e["text"].lower() == "sparkle" for e in entities)

    # Check action extraction
    assert "actions" in data
    assert "steal" in data["actions"]  # Lemmatized from "stealing"


@pytest.mark.asyncio
async def test_memory_validation(test_client, mock_ollama_response):
    """Test content validation rules."""
    # Test empty content
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store", json={"content": ""}
    )
    assert response.status_code == 400
    assert "error" in response.json()

    # Test whitespace-only content
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store", json={"content": "   \n\t   "}
    )
    assert response.status_code == 400

    # Test content too long (over 7500 chars)
    long_content = "x" * 7501
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store", json={"content": long_content}
    )
    assert response.status_code == 400
