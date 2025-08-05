"""Test fixtures for embeddings."""

import pytest

from pond.services.embeddings import EmbeddingProvider
from pond.services.embeddings.mock import MockEmbedding


@pytest.fixture
def mock_embedding_provider() -> EmbeddingProvider:
    """Provide a mock embedding provider for tests."""
    return MockEmbedding(dimension=768)


@pytest.fixture
def mock_embedding_provider_small() -> EmbeddingProvider:
    """Provide a mock embedding provider with smaller dimension."""
    return MockEmbedding(dimension=384)
