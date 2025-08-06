"""Base protocol and exceptions for embedding providers."""

from typing import Protocol

import numpy as np


class EmbeddingError(Exception):
    """Base exception for all embedding-related errors."""

    pass


class EmbeddingServiceUnavailable(EmbeddingError):  # noqa: N818
    """Raised when the embedding service is unreachable."""

    pass


class EmbeddingModelNotFound(EmbeddingError):  # noqa: N818
    """Raised when the requested model doesn't exist."""

    pass


class EmbeddingTimeout(EmbeddingError):  # noqa: N818
    """Raised when embedding generation times out."""

    pass


class EmbeddingInvalidInput(EmbeddingError):  # noqa: N818
    """Raised when input text is invalid (empty, too long, etc.)."""

    pass


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers.

    Contract:
    - All methods must raise EmbeddingError subclasses on failure
    - No silent failures or None returns
    - Implementations should fail fast and provide clear error messages
    - Health check should complete quickly (<5s)
    """

    @property
    def model_name(self) -> str:
        """Return the model name for logging/debugging."""
        ...

    @property
    def dimension(self) -> int:
        """Return the embedding dimension (e.g., 768, 1536)."""
        ...

    async def embed(self, text: str) -> np.ndarray:
        """Generate embedding for the given text.

        Args:
            text: Text to embed (must be non-empty)

        Returns:
            numpy array of shape (dimension,)

        Raises:
            EmbeddingServiceUnavailable: Can't reach the service
            EmbeddingModelNotFound: Model doesn't exist
            EmbeddingTimeout: Request timed out
            EmbeddingInvalidInput: Text is empty or invalid
        """
        ...

    async def health_check(self) -> dict:
        """Check embedding service health.

        Returns JSON-compatible dict with at least:
        - healthy: bool
        - service: str (provider name)
        - model: str (model name)
        - dimension: int

        Optional fields:
        - latency_ms: float (test embedding generation time)
        - error: str (if unhealthy)
        - endpoint: str (service URL if applicable)

        Should complete quickly and not throw exceptions.
        """
        ...
