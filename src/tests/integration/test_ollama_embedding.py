"""Integration tests for Ollama embedding provider."""

import numpy as np
import pytest

from pond.services.embeddings import (
    EmbeddingInvalidInput,
)
from pond.services.embeddings.ollama import OllamaEmbedding

# Mark all tests in this module to skip if Ollama isn't available
pytestmark = pytest.mark.skipif(
    "not config.getoption('--run-ollama')",
    reason="Need --run-ollama flag to run Ollama integration tests",
)


@pytest.fixture
async def ollama_provider():
    """Create Ollama provider for testing."""
    provider = OllamaEmbedding()

    # Check if Ollama is actually running
    health = await provider.health_check()
    if not health["healthy"]:
        pytest.skip(f"Ollama not available: {health.get('error', 'Unknown error')}")

    return provider


class TestOllamaIntegration:
    """Integration tests for Ollama embedding provider."""

    @pytest.mark.asyncio
    async def test_generate_embedding(self, ollama_provider):
        """Test generating a real embedding."""
        text = "The quick brown fox jumps over the lazy dog"
        embedding = await ollama_provider.embed(text)

        # Check shape - nomic-embed-text uses 768 dimensions
        assert embedding.shape == (768,)
        assert embedding.dtype.name == "float32"

        # Check it's not all zeros
        assert not np.allclose(embedding, 0)

        # Embeddings are typically normalized
        norm = np.linalg.norm(embedding)
        assert 0.9 < norm < 1.1  # Close to unit length

    @pytest.mark.asyncio
    async def test_similar_texts_similar_embeddings(self, ollama_provider):
        """Test that similar texts have similar embeddings."""
        text1 = "I love programming in Python"
        text2 = "I enjoy coding with Python"
        text3 = "The weather is nice today"

        embed1 = await ollama_provider.embed(text1)
        embed2 = await ollama_provider.embed(text2)
        embed3 = await ollama_provider.embed(text3)

        # Cosine similarity
        def cosine_sim(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_12 = cosine_sim(embed1, embed2)  # Similar texts
        sim_13 = cosine_sim(embed1, embed3)  # Different texts

        # Similar texts should have higher similarity
        assert sim_12 > sim_13
        assert sim_12 > 0.7  # Reasonably similar
        assert sim_13 < 0.5  # Not very similar

    @pytest.mark.asyncio
    async def test_empty_text_error(self, ollama_provider):
        """Test that empty text raises appropriate error."""
        with pytest.raises(EmbeddingInvalidInput, match="empty or whitespace"):
            await ollama_provider.embed("")

        with pytest.raises(EmbeddingInvalidInput, match="empty or whitespace"):
            await ollama_provider.embed("   \n\t  ")

    @pytest.mark.asyncio
    async def test_very_long_text(self, ollama_provider):
        """Test handling of very long text."""
        # Create text that's too long
        long_text = "x" * 60000

        with pytest.raises(EmbeddingInvalidInput, match="Text too long"):
            await ollama_provider.embed(long_text)

    @pytest.mark.asyncio
    async def test_health_check(self, ollama_provider):
        """Test health check provides expected information."""
        health = await ollama_provider.health_check()

        assert health["healthy"] is True
        assert health["service"] == "ollama"
        assert health["model"] == "nomic-embed-text"
        assert health["dimension"] == 768
        assert "latency_ms" in health
        assert health["latency_ms"] > 0
        assert health["endpoint"] == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_dimension_property(self, ollama_provider):
        """Test dimension property after first embedding."""
        # Before any embedding, dimension might not be known
        try:
            dim = ollama_provider.dimension
        except RuntimeError as e:
            assert "Dimension unknown" in str(e)

        # Generate an embedding
        await ollama_provider.embed("test")

        # Now dimension should be available
        assert ollama_provider.dimension == 768
