"""Mock embedding provider for testing."""

import hashlib
from typing import Any

import numpy as np

from .base import EmbeddingInvalidInput


class MockEmbedding:
    """Mock embedding provider for testing.

    Generates deterministic embeddings based on text hash.
    """

    def __init__(self, dimension: int = 768):
        """Initialize with configurable dimension."""
        self._dimension = dimension
        self._call_count = 0
        self._last_text = None

    @property
    def model_name(self) -> str:
        """Return the model name for logging/debugging."""
        return f"mock-{self._dimension}d"

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension

    async def embed(self, text: str) -> np.ndarray:
        """Generate deterministic embedding from text hash."""
        if not text or not text.strip():
            raise EmbeddingInvalidInput("Text cannot be empty or whitespace-only")

        # Track calls for testing
        self._call_count += 1
        self._last_text = text

        # Generate deterministic embedding from hash
        # This ensures same text always gets same embedding
        text_hash = hashlib.sha256(text.encode()).digest()

        # Use hash bytes to seed random generator
        rng = np.random.RandomState(int.from_bytes(text_hash[:4], "big"))

        # Generate embedding in [-1, 1] range (like real embeddings)
        embedding = rng.uniform(-1, 1, size=self._dimension).astype(np.float32)

        # Normalize to unit length (common for embeddings)
        embedding = embedding / np.linalg.norm(embedding)

        return embedding

    async def health_check(self) -> dict[str, Any]:
        """Mock health check - always healthy."""
        return {
            "healthy": True,
            "service": "mock",
            "model": self.model_name,
            "dimension": self._dimension,
            "call_count": self._call_count,
        }
