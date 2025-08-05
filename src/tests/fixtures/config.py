"""Configuration fixtures for testing."""

from unittest.mock import MagicMock

import pytest

from pond.config import Settings


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    settings = MagicMock(spec=Settings)
    settings.embedding_provider = "mock"
    settings.database_url = "postgresql://localhost:5432/pond_test"
    settings.ollama_url = "http://localhost:11434"
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.ollama_embedding_timeout = 60
    settings.api_key = "test-key"
    settings.db_pool_min_size = 10
    settings.db_pool_max_size = 20
    return settings
