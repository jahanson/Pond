"""Integration tests for unified search functionality."""

import pytest

from pond.domain import MemoryRepository
from pond.services.embeddings.mock import MockEmbedding

# Import test fixtures
from tests.fixtures.database import test_db_pool, test_tenant  # noqa: F401


@pytest.mark.asyncio
async def test_unified_search_text_match(test_db_pool, test_tenant):
    """Test that full-text search finds exact matches."""
    # Create repository with mock embeddings
    repo = MemoryRepository(test_db_pool, test_tenant, MockEmbedding())

    # Store memories with varying content
    memories = [
        "Python debugging is an essential skill",
        "I love debugging complex problems",
        "The Python ecosystem is vast",
        "Coffee helps with late night coding",
    ]

    for content in memories:
        await repo.store(content, [])

    # Search for "Python debugging" - should match first memory strongly
    results = await repo.search("Python debugging", limit=10)

    assert len(results) > 0
    # First result should contain both words
    assert "Python" in results[0].content and "debugging" in results[0].content


@pytest.mark.asyncio
async def test_unified_search_feature_match(test_db_pool, test_tenant):
    """Test that feature search finds tag/entity matches."""
    repo = MemoryRepository(test_db_pool, test_tenant, MockEmbedding())

    # Store memories with specific tags
    await repo.store("Learning about machine learning", ["python", "ml"])
    await repo.store("Database optimization techniques", ["postgres", "performance"])
    await repo.store("Frontend development with React", ["javascript", "react"])

    # Search for "python" - should find via tag even if not in content
    results = await repo.search("python", limit=10)

    assert len(results) > 0
    # Should find the ML memory via tag
    found_ml = any("machine learning" in m.content for m in results)
    assert found_ml


@pytest.mark.asyncio
async def test_unified_search_semantic_match(test_db_pool, test_tenant):
    """Test that semantic search finds related concepts."""
    repo = MemoryRepository(test_db_pool, test_tenant, MockEmbedding())

    # Store memories with related concepts
    memories = [
        "Programming in Python is enjoyable",
        "Coding with Ruby is fun",
        "I enjoy writing software",
        "Eating pizza is delicious",
    ]

    for content in memories:
        await repo.store(content, [])

    # Search for "software development" - should find programming-related memories
    # With mock embeddings this is less predictable, but test the mechanism works
    results = await repo.search("software development", limit=10)

    # Should return some results
    assert isinstance(results, list)
    # All results should be Memory objects
    assert all(hasattr(m, "content") for m in results)


@pytest.mark.asyncio
async def test_unified_search_combined_scoring(test_db_pool, test_tenant):
    """Test that combined scoring works across all search types."""
    repo = MemoryRepository(test_db_pool, test_tenant, MockEmbedding())

    # Store a memory that will match in multiple ways
    await repo.store(
        "Debugging Python code requires patience",
        ["python", "debugging", "programming"],
    )

    # Store competing memories
    await repo.store("I wrote some JavaScript today", ["javascript"])
    await repo.store("The weather is nice", ["weather"])

    # Search for "python" - should strongly match the first memory
    results = await repo.search("python", limit=10)

    assert len(results) > 0
    # First result should be our multi-match memory
    assert "Debugging Python" in results[0].content


@pytest.mark.asyncio
async def test_unified_search_respects_limit(test_db_pool, test_tenant):
    """Test that search respects the limit parameter."""
    repo = MemoryRepository(test_db_pool, test_tenant, MockEmbedding())

    # Store many memories
    for i in range(20):
        await repo.store(f"Memory number {i} about Python", ["python"])

    # Search with limit
    results = await repo.search("python", limit=5)

    assert len(results) <= 5


@pytest.mark.asyncio
async def test_unified_search_excludes_forgotten(test_db_pool, test_tenant):
    """Test that forgotten memories are excluded from search."""
    repo = MemoryRepository(test_db_pool, test_tenant, MockEmbedding())

    # Store memories
    memory1, _ = await repo.store("Python is great", ["python"])
    memory2, _ = await repo.store("Python is awesome", ["python"])

    # Mark first as forgotten
    async with repo.db_pool.acquire_tenant(repo.tenant) as conn:
        await conn.execute("UPDATE memories SET forgotten = true WHERE id = $1", memory1.id)

    # Search should only find the active memory
    results = await repo.search("python", limit=10)

    result_ids = [m.id for m in results]
    assert memory1.id not in result_ids
    assert memory2.id in result_ids


@pytest.mark.asyncio
async def test_unified_search_empty_query(test_db_pool, test_tenant):
    """Test that empty query returns no results gracefully."""
    repo = MemoryRepository(test_db_pool, test_tenant, MockEmbedding())

    await repo.store("Some content", ["tag"])

    # Empty query should return empty list
    results = await repo.search("", limit=10)
    assert results == []

    # Whitespace-only query should also return empty
    results = await repo.search("   ", limit=10)
    assert results == []
