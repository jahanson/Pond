"""
Unit tests for embedding functionality.
"""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_ollama_embedding_request_format():
    """Test that we send the correct request to Ollama."""
    # This is what we expect to send to Ollama
    expected_url = "http://localhost:11434/api/embeddings"
    expected_json = {
        "model": "nomic-embed-text",
        "prompt": "Test memory content"
    }

    # Mock the httpx client
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_post.return_value = mock_response

        # This is what our embedding service should do
        from pond.services.embeddings import get_embedding
        result = await get_embedding("Test memory content")

        # Verify the call
        mock_post.assert_called_once_with(
            expected_url,
            json=expected_json
        )
        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)


@pytest.mark.asyncio
async def test_handle_ollama_connection_error():
    """Test graceful handling when Ollama is unavailable."""
    with patch("httpx.AsyncClient.post") as mock_post:
        # Simulate connection error
        mock_post.side_effect = Exception("Connection refused")

        from pond.services.embeddings import get_embedding

        # Should raise a more specific error
        with pytest.raises(Exception) as exc_info:
            await get_embedding("Test content")

        assert "embedding service" in str(exc_info.value).lower()
