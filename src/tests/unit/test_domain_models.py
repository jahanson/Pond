"""Tests for domain models."""
import pytest

from pond.models import Tag, Entity, Action, Memory, ValidationError, MAX_CONTENT_LENGTH


class TestTag:
    """Test the Tag domain object."""
    
    def test_tag_normalization(self):
        """Test that tags normalize themselves."""
        tag = Tag("Python Tips")
        assert tag.raw == "Python Tips"
        assert tag.normalized == "python-tip"
    
    def test_tag_equality(self):
        """Test that tags with same normalized form are equal."""
        tag1 = Tag("children's stories")
        tag2 = Tag("stories for children")
        tag3 = Tag("cats")
        
        assert tag1 == tag2  # Both normalize to "child-story"
        assert tag1 != tag3  # Different normalized forms
    
    def test_tag_in_set(self):
        """Test that normalized tags work in sets."""
        tags = {
            Tag("python tips"),
            Tag("Python Tips"),  # Duplicate!
            Tag("tips python"),  # Also duplicate!
            Tag("debugging"),
        }
        
        # Should only have 2 unique tags
        assert len(tags) == 2
        
        # Check the normalized forms
        normalized = {tag.normalized for tag in tags}
        assert normalized == {"python-tip", "debug"}
    
    def test_tag_caching(self):
        """Test that normalization is cached."""
        tag = Tag("machine learning")
        
        # First access computes it
        norm1 = tag.normalized
        
        # Second access should return cached value
        # (We can't easily test this without mocking, but it should be the same)
        norm2 = tag.normalized
        
        assert norm1 == norm2 == "learn-machine"


class TestMemory:
    """Test the Memory domain object."""
    
    def test_memory_creation(self):
        """Test creating a memory."""
        memory = Memory(content="Sparkle stole pizza from the counter")
        
        assert memory.content == "Sparkle stole pizza from the counter"
        assert memory.active is True
        assert memory.tags == []
        assert memory.entities == []
        assert memory.actions == []
    
    def test_memory_validation_on_creation(self):
        """Test that memories validate themselves on creation."""
        # Valid memory
        memory = Memory(content="Valid content")
        assert memory.content == "Valid content"
        
        # Empty content raises
        with pytest.raises(ValidationError, match="Content cannot be empty"):
            Memory(content="")
        
        # Whitespace only raises
        with pytest.raises(ValidationError, match="Content cannot be only whitespace"):
            Memory(content="   ")
        
        # Too long raises
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            Memory(content="x" * (MAX_CONTENT_LENGTH + 1))
    
    def test_memory_at_max_length(self):
        """Test memory exactly at max length is allowed."""
        content = "x" * MAX_CONTENT_LENGTH
        memory = Memory(content=content)
        assert len(memory.content) == MAX_CONTENT_LENGTH
    
    def test_add_tags_deduplication(self):
        """Test that add_tags deduplicates in normalized space."""
        memory = Memory(content="Learning about Python")
        
        # Add various forms of the same tags
        memory.add_tags(
            "python tips",
            "Python Tips",  # Duplicate
            Tag("tips python"),  # Also duplicate
            "machine learning"
        )
        
        # Should only have 2 unique tags
        assert len(memory.tags) == 2
        
        # Check the raw forms are preserved
        raw_tags = [tag.raw for tag in memory.tags]
        assert "python tips" in raw_tags  # First one wins
        assert "machine learning" in raw_tags
    
    def test_get_normalized_tags(self):
        """Test getting normalized tag strings."""
        memory = Memory(content="Test")
        memory.add_tags("Python Tips", "debugging sessions", "async programming")
        
        normalized = memory.get_normalized_tags()
        assert set(normalized) == {"python-tip", "debugging-session", "async-programming"}
    
    def test_memory_to_dict(self):
        """Test serializing memory to dictionary."""
        memory = Memory(
            id=42,
            content="Test memory",
        )
        memory.add_tags("python", "testing")
        memory.entities.append(Entity(text="Python", type="LANGUAGE"))
        memory.actions.append(Action(lemma="test"))
        
        data = memory.to_dict()
        
        assert data["id"] == 42
        assert data["content"] == "Test memory"
        assert data["tags"] == ["python", "testing"]
        assert data["entities"] == [{"text": "Python", "type": "LANGUAGE"}]
        assert data["actions"] == ["test"]
        assert data["active"] is True


class TestDomainModelInteraction:
    """Test how domain models work together."""
    
    def test_memory_with_rich_features(self):
        """Test a memory with all features."""
        memory = Memory(content="Sparkle stole pizza from the counter yesterday")
        
        # Add user tags
        memory.add_tags("cats", "sparkle theft", "funny")
        
        # Simulate what the repository would do
        memory.entities.extend([
            Entity(text="Sparkle", type="PERSON"),  # Cat names often recognized as PERSON
            Entity(text="yesterday", type="DATE"),
        ])
        
        memory.actions.extend([
            Action(lemma="steal"),
        ])
        
        # Check the memory has all features
        assert len(memory.tags) == 3
        assert len(memory.entities) == 2
        assert len(memory.actions) == 1
        
        # Tags should be normalized internally
        assert "cat" in memory.get_normalized_tags()  # "cats" -> "cat"
        assert "funny" in memory.get_normalized_tags()
        assert "sparkle-theft" in memory.get_normalized_tags()