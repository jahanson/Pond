"""Integration tests for MemoryRepository with real database."""

import numpy as np
import pendulum
import pytest

from pond.domain import Memory, MemoryRepository

# Import test fixtures are used as pytest fixture parameters below
from tests.fixtures.database import test_db_pool, test_tenant  # noqa: F401


@pytest.fixture
async def test_repository(test_db_pool, test_tenant):
    """Create a test repository with database."""
    repo = MemoryRepository(test_db_pool, test_tenant)
    yield repo
    # Cleanup handled by test_tenant fixture


@pytest.mark.asyncio
async def test_store_and_retrieve_memory(test_repository):
    """Test storing a memory and getting it back."""
    # Store a memory
    content = "I learned that Python's walrus operator := can simplify comprehensions"
    tags = ["python", "programming", "learning"]

    stored_memory, splash = await test_repository.store(content, tags)

    # Check stored memory
    assert stored_memory.id is not None
    assert stored_memory.content == content
    assert stored_memory.embedding is not None
    assert stored_memory.embedding.shape == (768,)

    # Check tags (should include user tags + auto-generated)
    all_tags = stored_memory.get_tags()
    assert "python" in all_tags
    assert "programming" in all_tags
    assert "learn" in all_tags  # "learning" is normalized to "learn"

    # Splash should be empty (no similar memories yet)
    assert splash == []




@pytest.mark.asyncio
async def test_search_mechanics(test_repository):
    """Test search method executes without errors (not testing embedding quality)."""
    # Store a memory
    content = "Python is great for data science"
    stored_memory, _ = await test_repository.store(content, ["python"])

    # Search should execute without errors
    # Note: With random embeddings, we can't predict what will be returned
    results = await test_repository.search("anything", limit=10)

    # Just verify it returns a list (may be empty due to random similarities)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_get_recent_memories(test_repository):
    """Test retrieving recent memories."""
    # Store memories at different times
    now = pendulum.now("UTC")

    # Old memory (2 hours ago)
    old_memory = Memory(content="Old memory")
    old_memory.metadata["created_at"] = now.subtract(hours=2).isoformat()
    old_memory.embedding = np.random.rand(768)
    await test_repository._store_in_db(old_memory)

    # Recent memory (30 minutes ago)
    recent_memory = Memory(content="Recent memory")
    recent_memory.metadata["created_at"] = now.subtract(minutes=30).isoformat()
    recent_memory.embedding = np.random.rand(768)
    await test_repository._store_in_db(recent_memory)

    # Get memories from last hour
    since = now.subtract(hours=1)
    recent = await test_repository.get_recent(since, limit=10)

    assert len(recent) == 1
    assert recent[0].content == "Recent memory"


@pytest.mark.asyncio
async def test_memory_round_trip(test_repository):
    """Test that all memory fields survive database round trip."""
    # Create a memory with all features
    memory = Memory(content="Test memory with all features")
    memory.add_tags("test", "integration", "database")
    memory.add_entity(("PostgreSQL", "TECH"))
    memory.add_entity(("Python", "LANGUAGE"))
    memory.add_action("test")
    memory.add_action("verify")

    # Store it
    stored, _ = await test_repository.store(memory.content, ["test", "integration", "database"])

    # Retrieve it
    recent = await test_repository.get_recent(pendulum.now("UTC").subtract(minutes=1))
    retrieved = recent[0]

    # Verify all data survived
    assert retrieved.id == stored.id
    assert retrieved.content == stored.content
    assert set(retrieved.get_tags()) == set(stored.get_tags())

    # Note: Entities and actions from manual adds won't be there
    # because store() re-extracts features. But the extraction
    # should find similar things from the content.
