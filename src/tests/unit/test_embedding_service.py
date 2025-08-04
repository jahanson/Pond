"""
Unit tests for the embedding service architecture.
"""
import pytest

from pond.services.embeddings import EmbeddingService, SpacyTagEmbedder, SimpleTagEmbedder


class TestEmbeddingService:
    """Test the unified embedding service."""

    def test_tag_embedding_basic(self):
        """Test basic tag embedding functionality."""
        service = EmbeddingService()
        
        # Single tag
        assert service.embed_tag("Python") == "python"
        assert service.embed_tag("machine learning") == "learn-machine"

    def test_tag_embedding_deduplication(self):
        """Test that embed_tags deduplicates in embedding space."""
        service = EmbeddingService()
        
        # These should deduplicate to just one tag
        tags = ["python tips", "Python Tips", "tips python"]
        embedded = service.embed_tags(tags)
        
        assert len(embedded) == 1
        assert embedded[0] == "python-tip"

    def test_tag_embedding_preserves_order(self):
        """Test that first occurrence order is preserved."""
        service = EmbeddingService()
        
        tags = ["cats", "dogs", "cats", "birds"]
        embedded = service.embed_tags(tags)
        
        assert embedded == ["cat", "dog", "bird"]

    def test_tag_embedding_filters_empty(self):
        """Test that empty tags are filtered out."""
        service = EmbeddingService()
        
        tags = ["python", "", None, "  ", "debugging"]
        embedded = service.embed_tags(tags)
        
        assert embedded == ["python", "debug"]  # "debugging" lemmatizes to "debug"

    def test_semantic_equivalence(self):
        """Test that semantically equivalent tags converge."""
        service = EmbeddingService()
        
        # All of these should embed to the same string
        variants = [
            "children's stories",
            "stories for children",
            "children stories",
            "story for children"
        ]
        
        embedded = [service.embed_tag(tag) for tag in variants]
        
        # All should be the same
        assert len(set(embedded)) == 1
        assert embedded[0] == "child-story"

    def test_custom_tag_embedder(self):
        """Test using a custom tag embedder."""
        simple_embedder = SimpleTagEmbedder()
        service = EmbeddingService(tag_embedder=simple_embedder)
        
        # Simple embedder doesn't do lemmatization but still uses hyphens
        assert service.embed_tag("Running shoes") == "running-shoes"

    @pytest.mark.asyncio
    async def test_content_embedding_not_implemented(self):
        """Test that content embedding raises NotImplementedError."""
        service = EmbeddingService()
        
        with pytest.raises(NotImplementedError):
            await service.embed_content("Some content to embed")