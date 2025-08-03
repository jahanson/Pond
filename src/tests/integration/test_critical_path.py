"""
Critical path tests for Pond's core functionality.
"""
import pytest


@pytest.mark.asyncio
async def test_store_memory_with_splashback(test_client, mock_ollama_response):
    """Test that storing a memory returns relevant splashback memories."""
    # Store first memory about Sparkle
    response1 = await test_client.post("/api/v1/test_tenant/store", json={
        "content": "Sparkle stole pizza from the counter",
        "tags": ["sparkle", "theft", "pizza"]
    })
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["splashback"] == []  # First memory has no splashback
    
    # Store second memory about Sparkle
    response2 = await test_client.post("/api/v1/test_tenant/store", json={
        "content": "Sparkle stole bacon this morning",
        "tags": ["sparkle", "theft", "bacon"]
    })
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Should get splashback with the pizza memory
    assert len(data2["splashback"]) > 0
    assert "pizza" in data2["splashback"][0]["content"]
    assert data2["splashback"][0]["similarity"] > 0.7


@pytest.mark.asyncio
async def test_tenant_isolation(test_client, mock_ollama_response):
    """Test that memories are isolated between tenants."""
    # Store memory for Claude
    await test_client.post("/api/v1/claude/store", json={
        "content": "Claude's private thought about Python",
        "tags": ["python", "private"]
    })
    
    # Store memory for Alpha
    await test_client.post("/api/v1/alpha/store", json={
        "content": "Alpha's private thought about JavaScript",
        "tags": ["javascript", "private"]
    })
    
    # Search Claude's memories
    claude_response = await test_client.post("/api/v1/claude/search", json={
        "query": "private thought",
        "limit": 10
    })
    claude_memories = claude_response.json()["memories"]
    
    # Claude should only see their own memory
    assert len(claude_memories) == 1
    assert "Python" in claude_memories[0]
    assert "JavaScript" not in claude_memories[0]
    
    # Search Alpha's memories
    alpha_response = await test_client.post("/api/v1/alpha/search", json={
        "query": "private thought",
        "limit": 10
    })
    alpha_memories = alpha_response.json()["memories"]
    
    # Alpha should only see their own memory
    assert len(alpha_memories) == 1
    assert "JavaScript" in alpha_memories[0]
    assert "Python" not in alpha_memories[0]


@pytest.mark.asyncio
async def test_memory_init_returns_recent_and_context(test_client, mock_ollama_response):
    """Test that init returns personality context and recent memories."""
    # Store some memories first
    memories = [
        "User prefers uv over pip for Python",
        "Sparkle is a criminal mastermind cat",
        "We debugged a semicolon for 2 hours"
    ]
    
    for memory in memories:
        await test_client.post("/api/v1/test_tenant/store", json={
            "content": memory
        })
    
    # Call init
    response = await test_client.post("/api/v1/test_tenant/init")
    assert response.status_code == 200
    
    data = response.json()
    assert "context" in data
    assert "recent_memories" in data
    
    # Should have our recent memories
    assert len(data["recent_memories"]) > 0
    # Most recent memories should include what we just stored
    recent_contents = " ".join(data["recent_memories"])
    assert "Sparkle" in recent_contents or "semicolon" in recent_contents


@pytest.mark.asyncio
async def test_search_by_semantic_similarity(test_client, mock_ollama_response):
    """Test semantic search finds related memories."""
    # Store memories about different topics
    await test_client.post("/api/v1/test_tenant/store", json={
        "content": "Sparkle stole pizza again"
    })
    await test_client.post("/api/v1/test_tenant/store", json={
        "content": "Python debugging is frustrating"
    })
    await test_client.post("/api/v1/test_tenant/store", json={
        "content": "Sparkle's criminal activities continue"
    })
    
    # Search for cat-related memories
    response = await test_client.post("/api/v1/test_tenant/search", json={
        "query": "cat theft",
        "limit": 10
    })
    
    memories = response.json()["memories"]
    # Should find Sparkle memories but not Python
    sparkle_count = sum(1 for m in memories if "Sparkle" in m)
    python_count = sum(1 for m in memories if "Python" in m)
    
    assert sparkle_count >= 2
    assert python_count == 0


@pytest.mark.asyncio
async def test_get_recent_memories(test_client, mock_ollama_response):
    """Test retrieving recent memories within time window."""
    # Store a memory
    await test_client.post("/api/v1/test_tenant/store", json={
        "content": "Just stored this memory"
    })
    
    # Get recent memories
    response = await test_client.post("/api/v1/test_tenant/recent", json={
        "hours": 1,
        "limit": 10
    })
    
    assert response.status_code == 200
    memories = response.json()["memories"]
    assert len(memories) > 0
    assert "Just stored this memory" in memories[0]


@pytest.mark.asyncio
async def test_splashback_similarity_threshold(test_client, mock_ollama_response):
    """Test that splashback only returns memories within similarity range."""
    # This test would need different embeddings to test properly
    # For now, we'll test the structure
    
    # Store multiple memories
    for i in range(5):
        await test_client.post("/api/v1/test_tenant/store", json={
            "content": f"Memory number {i}"
        })
    
    # Store one more and check splashback
    response = await test_client.post("/api/v1/test_tenant/store", json={
        "content": "Final memory"
    })
    
    splashback = response.json()["splashback"]
    # Should have at most 3 memories (as defined in our design)
    assert len(splashback) <= 3
    
    # Each should have similarity score
    for memory in splashback:
        assert "content" in memory
        assert "similarity" in memory
        assert 0 <= memory["similarity"] <= 1