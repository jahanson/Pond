"""Factory for creating embedding providers."""

from pond.config import settings

from .base import EmbeddingError, EmbeddingProvider
from .mock import MockEmbedding
from .ollama import OllamaEmbedding


class EmbeddingNotConfigured(EmbeddingError):
    """Raised when embeddings are used but not configured."""

    pass


def get_embedding_provider() -> EmbeddingProvider:
    """Get the configured embedding provider.

    Uses EMBEDDING_PROVIDER from settings to determine
    which provider to instantiate.

    Returns:
        Configured embedding provider instance

    Raises:
        EmbeddingNotConfigured: If EMBEDDING_PROVIDER is not set
    """
    if settings.embedding_provider is None:
        raise EmbeddingNotConfigured(
            "Embedding service not configured. Set EMBEDDING_PROVIDER environment variable:\n"
            "  - EMBEDDING_PROVIDER=ollama (for Ollama embeddings)\n"
            "  - EMBEDDING_PROVIDER=mock (for testing)\n"
            "\nExample:\n"
            "  export EMBEDDING_PROVIDER=ollama\n"
            "  export OLLAMA_EMBEDDING_MODEL=nomic-embed-text"
        )

    # Settings already validates the provider name
    if settings.embedding_provider == "ollama":
        return OllamaEmbedding()
    elif settings.embedding_provider == "mock":
        return MockEmbedding()
    else:
        # This should never happen due to validation in settings
        raise ValueError(
            f"Unknown embedding provider: {settings.embedding_provider}. "
            f"Valid options: ollama, mock"
        )
