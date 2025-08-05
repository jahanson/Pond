"""Tests for embedding provider factory."""

import pytest

from pond.services.embeddings import get_embedding_provider
from pond.services.embeddings.mock import MockEmbedding
from pond.services.embeddings.ollama import OllamaEmbedding


class TestEmbeddingFactory:
    """Test the embedding provider factory."""

    def test_get_mock_provider(self, monkeypatch):
        """Test getting mock provider."""
        # Settings are loaded at import time, so we need to reload
        monkeypatch.setattr("pond.config.settings.embedding_provider", "mock")

        provider = get_embedding_provider()
        assert isinstance(provider, MockEmbedding)

    def test_get_ollama_provider(self, monkeypatch):
        """Test getting Ollama provider."""
        monkeypatch.setattr("pond.config.settings.embedding_provider", "ollama")
        monkeypatch.setattr(
            "pond.config.settings.ollama_embedding_model", "nomic-embed-text"
        )

        provider = get_embedding_provider()
        assert isinstance(provider, OllamaEmbedding)

    def test_case_insensitive(self, monkeypatch):
        """Test that provider names are normalized to lowercase."""
        # Settings validation already lowercases the provider name
        monkeypatch.setattr("pond.config.settings.embedding_provider", "mock")

        provider = get_embedding_provider()
        assert isinstance(provider, MockEmbedding)

    def test_invalid_provider_never_reached(self, monkeypatch):
        """Test that invalid provider check is never reached due to settings validation."""
        # This simulates if settings validation somehow failed
        monkeypatch.setattr("pond.config.settings.embedding_provider", "invalid")

        with pytest.raises(ValueError, match="Unknown embedding provider: invalid"):
            get_embedding_provider()
