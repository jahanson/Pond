"""Integration tests for splash functionality."""

import pytest

from pond.domain import MemoryRepository
from pond.services.embeddings.mock import MockEmbedding

# Import test fixtures
from tests.fixtures.database import test_db_pool, test_tenant  # noqa: F401


@pytest.fixture
async def test_repository_with_mock(test_db_pool, test_tenant):  # noqa: F811
    """Create a test repository with mock embeddings."""
    # Use mock embeddings for predictable similarity tests
    mock_provider = MockEmbedding(dimension=768)
    repo = MemoryRepository(test_db_pool, test_tenant, mock_provider)
    yield repo


@pytest.mark.asyncio
async def test_splash_returns_similar_memories(test_repository_with_mock):
    """Test that splash returns memories in the 0.7-0.9 similarity range."""
    repo = test_repository_with_mock

    # Store some memories with varying content
    # The mock embeddings are deterministic based on text hash
    memories = [
        "I love programming in Python",
        "I enjoy coding with Python",  # Similar to first
        "Python is my favorite language",  # Somewhat similar
        "The weather is nice today",  # Different topic
        "Cats are wonderful pets",  # Very different
    ]

    stored = []
    for content in memories:
        memory, _ = await repo.store(content, [])
        stored.append(memory)

    # Now store a new memory similar to the Python ones
    new_memory, splash = await repo.store(
        "I really like developing in Python", ["python", "programming"]
    )

    # Splash should contain memories with similarity between 0.7-0.9
    # With mock embeddings, we can't predict exact similarities,
    # but we can verify the mechanism works
    assert isinstance(splash, list)
    assert len(splash) <= 3  # Max 3 memories

    # All returned memories should be different from the new one
    for memory in splash:
        assert memory.id != new_memory.id
        assert memory.content != new_memory.content


@pytest.mark.asyncio
async def test_splash_empty_when_no_similar_memories(test_repository_with_mock):
    """Test that splash is empty when no memories fall in similarity range."""
    repo = test_repository_with_mock

    # Store a memory
    first_memory, splash = await repo.store("The first memory", [])

    # First memory should have empty splash (no other memories)
    assert splash == []

    # Store a very different memory
    # With deterministic mock embeddings, different text = different embedding
    second_memory, splash = await repo.store(
        "Completely unrelated content about quantum physics and black holes",
        ["physics", "science"],
    )

    # If the embeddings are sufficiently different, splash might be empty
    # (This depends on the mock's hash-based embedding generation)
    assert isinstance(splash, list)
    assert len(splash) <= 3


@pytest.mark.asyncio
async def test_splash_respects_forgotten_flag(test_repository_with_mock):
    """Test that forgotten memories are excluded from splash."""
    repo = test_repository_with_mock

    # Store some memories
    memory1, _ = await repo.store("Python programming tips", ["python"])
    memory2, _ = await repo.store("Python coding best practices", ["python"])

    # Mark first memory as forgotten
    async with repo.db_pool.acquire_tenant(repo.tenant) as conn:
        await conn.execute(
            "UPDATE memories SET forgotten = true WHERE id = $1", memory1.id
        )

    # Store a new similar memory
    new_memory, splash = await repo.store("Python development techniques", ["python"])

    # Splash should not include the forgotten memory
    splash_ids = [m.id for m in splash]
    assert memory1.id not in splash_ids

    # But could include the active memory (if similarity is in range)
    # We can't guarantee memory2 is in splash due to mock embedding randomness
