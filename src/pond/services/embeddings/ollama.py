"""Ollama embedding provider implementation."""

import time
from typing import Any

import aiohttp
import numpy as np

from pond.config import settings

from .base import (
    EmbeddingInvalidInput,
    EmbeddingModelNotFound,
    EmbeddingServiceUnavailable,
    EmbeddingTimeout,
)


class OllamaEmbedding:
    """Embedding provider using Ollama service."""

    def __init__(self):
        """Initialize from environment configuration."""
        # Read from settings
        self.url = settings.ollama_url
        self.model = settings.ollama_embedding_model
        self.timeout = settings.ollama_embedding_timeout
        self._dimension = None  # Lazy load on first embed

    @property
    def model_name(self) -> str:
        """Return the model name for logging/debugging."""
        return self.model

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        if self._dimension is None:
            raise RuntimeError(
                "Dimension unknown until first embedding generated. "
                "Call health_check() or embed() first."
            )
        return self._dimension

    async def embed(self, text: str) -> np.ndarray:
        """Generate embedding for the given text using Ollama."""
        # Validate input
        if not text or not text.strip():
            raise EmbeddingInvalidInput("Text cannot be empty or whitespace-only")

        # Ollama has a practical limit, but it's quite high
        # Let's be reasonable to avoid massive API calls
        if len(text) > 50000:
            raise EmbeddingInvalidInput(f"Text too long: {len(text)} chars (max 50000)")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status == 404:
                        # Model not found
                        error_data = await response.json()
                        raise EmbeddingModelNotFound(
                            f"Model '{self.model}' not found: {error_data.get('error', 'Unknown error')}"
                        )
                    elif response.status != 200:
                        # Other errors
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("error", "Unknown error")
                        except Exception:
                            error_msg = f"HTTP {response.status}"
                        raise EmbeddingServiceUnavailable(f"Ollama error: {error_msg}")

                    # Success
                    data = await response.json()
                    embedding = np.array(data["embedding"], dtype=np.float32)

                    # Store dimension on first successful call
                    if self._dimension is None:
                        self._dimension = len(embedding)

                    return embedding

        except TimeoutError as e:
            raise EmbeddingTimeout(
                f"Ollama embedding timed out after {self.timeout}s. "
                "This often happens on first model load."
            ) from e
        except aiohttp.ClientError as e:
            raise EmbeddingServiceUnavailable(
                f"Cannot connect to Ollama at {self.url}: {e}"
            ) from e

    async def health_check(self) -> dict[str, Any]:
        """Check Ollama service health."""
        result = {
            "healthy": False,
            "service": "ollama",
            "model": self.model,
            "dimension": self._dimension or "unknown",
            "endpoint": self.url,
        }

        try:
            # First check if service is reachable
            time.perf_counter()

            async with aiohttp.ClientSession() as session:
                # Check if Ollama is running
                async with session.get(
                    f"{self.url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status != 200:
                        result["error"] = f"Service returned {response.status}"
                        return result

                    # Check if our model exists
                    data = await response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    if self.model not in models:
                        result["error"] = f"Model '{self.model}' not installed"
                        return result

                # Try a test embedding to check everything works
                # and to get dimension if we don't have it yet
                test_start = time.perf_counter()
                embedding = await self.embed("health check")
                latency_ms = (time.perf_counter() - test_start) * 1000

                result.update(
                    {
                        "healthy": True,
                        "dimension": len(embedding),
                        "latency_ms": round(latency_ms, 1),
                    }
                )

                # Update our cached dimension
                if self._dimension is None:
                    self._dimension = len(embedding)

        except Exception as e:
            result["error"] = str(e)

        return result
