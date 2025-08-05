"""Unit tests for embedding providers."""

import numpy as np
import pytest

from pond.services.embeddings import (
    EmbeddingInvalidInput,
    EmbeddingProvider,
)
from pond.services.embeddings.mock import MockEmbedding


class TestMockEmbedding:
    """Test the mock embedding provider."""

    @pytest.mark.asyncio
    async def test_basic_embedding(self):
        """Test basic embedding generation."""
        provider = MockEmbedding(dimension=768)

        embedding = await provider.embed("Hello, world!")

        assert embedding.shape == (768,)
        assert embedding.dtype.name == "float32"
        # Check it's normalized (unit length)
        assert abs(np.linalg.norm(embedding) - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_deterministic_embeddings(self):
        """Test that same text produces same embedding."""
        provider = MockEmbedding(dimension=384)

        text = "The quick brown fox"
        embed1 = await provider.embed(text)
        embed2 = await provider.embed(text)

        assert np.array_equal(embed1, embed2)

    @pytest.mark.asyncio
    async def test_different_texts_different_embeddings(self):
        """Test that different texts produce different embeddings."""
        provider = MockEmbedding()

        embed1 = await provider.embed("Hello")
        embed2 = await provider.embed("Goodbye")

        # They should be different
        assert not np.array_equal(embed1, embed2)

        # But both should be valid embeddings
        assert embed1.shape == embed2.shape == (768,)

    @pytest.mark.asyncio
    async def test_empty_text_raises_error(self):
        """Test that empty text raises appropriate error."""
        provider = MockEmbedding()

        with pytest.raises(EmbeddingInvalidInput, match="empty or whitespace"):
            await provider.embed("")

        with pytest.raises(EmbeddingInvalidInput, match="empty or whitespace"):
            await provider.embed("   ")

    @pytest.mark.asyncio
    async def test_provider_properties(self):
        """Test provider properties."""
        provider = MockEmbedding(dimension=512)

        assert provider.model_name == "mock-512d"
        assert provider.dimension == 512

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check method."""
        provider = MockEmbedding()

        # Initial health check
        health = await provider.health_check()
        assert health["healthy"] is True
        assert health["service"] == "mock"
        assert health["dimension"] == 768
        assert health["call_count"] == 0

        # After some embeddings
        await provider.embed("test1")
        await provider.embed("test2")

        health = await provider.health_check()
        assert health["call_count"] == 2

    @pytest.mark.asyncio
    async def test_provider_satisfies_protocol(self):
        """Test that MockEmbedding satisfies the EmbeddingProvider protocol."""
        provider = MockEmbedding()

        # This is a type check - if MockEmbedding doesn't satisfy
        # the protocol, mypy/pyright will complain
        def use_provider(p: EmbeddingProvider) -> None:
            pass

        use_provider(provider)  # Should not raise
