"""Tests for configuration management."""

import pytest
from pydantic import ValidationError

from pond.config import Settings


class TestSettings:
    """Test our custom Settings validation logic."""

    def test_ollama_requires_model(self, monkeypatch):
        """Test our custom validation that ollama provider requires model configuration."""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")
        monkeypatch.delenv("OLLAMA_EMBEDDING_MODEL", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert (
            "OLLAMA_EMBEDDING_MODEL is required when EMBEDDING_PROVIDER=ollama"
            in str(exc_info.value)
        )

    def test_mock_provider_no_extra_config(self, monkeypatch):
        """Test that mock provider doesn't require extra configuration."""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")

        # Should not raise
        settings = Settings()
        assert settings.embedding_provider == "mock"
        assert settings.ollama_embedding_model is None  # Not required for mock
