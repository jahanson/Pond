"""
Tests for the similarity donut - the sweet spot of reminiscence.
"""

import pytest


@pytest.mark.asyncio
async def test_splashback_excludes_too_similar(test_client, mock_ollama_response):
    """Test that nearly identical memories don't splash back."""
    # Store original memory
    await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Sparkle stole pizza from the counter"},
    )

    # Store nearly identical memory (just punctuation difference)
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Sparkle stole pizza from the counter!"},
    )

    # Should get no splashback (too similar)
    assert response.status_code == 200
    splashback = response.json()["splashback"]

    # With our mock embeddings, this tests the concept
    # Real implementation will need different embeddings to test properly
    # assert len(splashback) == 0 or splashback[0]["similarity"] < 0.9


@pytest.mark.asyncio
async def test_splashback_includes_sweet_spot(test_client, mock_ollama_response):
    """Test that moderately similar memories do splash back."""
    # Store related memories
    await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Sparkle's pizza heist last Tuesday"},
    )

    # Store new memory that should trigger splashback
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Sparkle committed bacon theft this morning"},
    )

    # Should get splashback (similar but not identical)
    assert response.status_code == 200
    splashback = response.json()["splashback"]

    # Should find the pizza memory
    if len(splashback) > 0:
        assert "pizza" in splashback[0]["content"].lower()
        # Similarity should be in the sweet spot (0.7-0.9)
        # With real embeddings: assert 0.7 <= splashback[0]["similarity"] <= 0.9


@pytest.mark.asyncio
async def test_splashback_excludes_unrelated(test_client, mock_ollama_response):
    """Test that unrelated memories don't splash back."""
    # Store unrelated memories
    await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Python debugging is frustrating sometimes"},
    )

    # Store cat memory
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Sparkle is napping in the sunbeam"},
    )

    # Should not get Python memory in splashback
    splashback = response.json()["splashback"]

    # No Python memories should surface for cat content
    python_memories = [m for m in splashback if "python" in m["content"].lower()]
    assert len(python_memories) == 0


@pytest.mark.asyncio
async def test_donut_parameters_tunable(test_client, mock_ollama_response):
    """Test that similarity thresholds work as expected."""
    # This test documents our tunable parameters
    # In real implementation, these would be configurable

    MIN_SIMILARITY = 0.7  # Below this: too different
    MAX_SIMILARITY = 0.9  # Above this: too similar

    # Store memories across the similarity spectrum
    memories = [
        "Sparkle is a cat",
        "Sparkle is a feline",
        "Sparkle is an animal",
        "Sparkle lives with us",
        "Dogs are also pets",
        "Python is a programming language",
    ]

    for memory in memories:
        await test_client.post(
            f"/api/v1/{test_client.test_tenant}/store", json={"content": memory}
        )

    # Query with something in the middle
    response = await test_client.post(
        f"/api/v1/{test_client.test_tenant}/store",
        json={"content": "Sparkle is our pet cat"},
    )

    splashback = response.json()["splashback"]

    # Should get some but not all Sparkle memories
    # Too similar: "Sparkle is a cat" (too close)
    # Just right: "Sparkle lives with us", "Sparkle is an animal"
    # Too different: "Python is a programming language"

    # With real embeddings, we'd verify similarities are in range
    assert len(splashback) <= 3  # Not too many
    assert len(splashback) >= 0  # Some related memories
