"""Tests for domain models."""
import pytest

from pond.domain import MAX_CONTENT_LENGTH, Action, Entity, Memory, Tag, ValidationError


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
        assert memory.forgotten is False
        assert memory.metadata["tags"] == set()
        assert memory.metadata["entities"] == []
        assert memory.metadata["actions"] == []
        assert "created_at" in memory.metadata

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

        # Should only have 2 unique tags (normalized)
        tags = memory.get_tags()
        assert len(tags) == 2
        assert "python-tip" in tags
        assert "learn-machine" in tags

    def test_get_tags(self):
        """Test getting normalized tag strings."""
        memory = Memory(content="Test")
        memory.add_tags("Python Tips", "debugging sessions", "async programming")

        tags = memory.get_tags()
        assert set(tags) == {"python-tip", "debugging-session", "async-programming"}

    def test_memory_to_dict(self):
        """Test serializing memory to dictionary."""
        memory = Memory(
            id=42,
            content="Test memory",
        )
        memory.add_tags("python", "testing")
        memory.add_entity(Entity("Python", "LANGUAGE"))
        memory.add_action(Action("test"))

        data = memory.to_dict()

        assert data["id"] == 42
        assert data["content"] == "Test memory"
        assert data["metadata"]["tags"] == ["python", "test"]  # Sorted, and "testing" normalized to "test"
        assert data["metadata"]["entities"] == [{"text": "Python", "type": "LANGUAGE"}]
        assert data["metadata"]["actions"] == [{"lemma": "test"}]
        assert data["forgotten"] is False

    def test_memory_from_dict(self):
        """Test deserializing memory from dictionary."""
        data = {
            "id": 42,
            "content": "Test memory",
            "forgotten": False,
            "embedding": [0.1, 0.2, 0.3],  # Small test embedding
            "metadata": {
                "created_at": "2024-01-01T00:00:00Z",
                "tags": ["python", "testing"],  # List from DB
                "entities": [{"text": "Python", "type": "LANGUAGE"}],
                "actions": [{"lemma": "test"}],
            }
        }

        memory = Memory.from_dict(data)

        assert memory.id == 42
        assert memory.content == "Test memory"
        assert memory.forgotten is False
        assert memory.embedding.shape == (3,)
        assert memory.metadata["tags"] == {"python", "testing"}  # Converted to set!
        assert memory.get_tags() == ["python", "testing"]  # Sorted list

        # Verify smart objects work
        entities = memory.get_entities()
        assert len(entities) == 1
        assert entities[0].text == "Python"
        assert entities[0].type == "LANGUAGE"


class TestMetadataItems:
    """Test Entity and Action smart objects."""

    def test_entity_behavior(self):
        """Test Entity smart object methods."""
        person = Entity("John Doe", "PERSON")
        location = Entity("New York", "GPE")
        org = Entity("OpenAI", "ORG")

        assert person.is_person() is True
        assert person.is_location() is False
        assert location.is_location() is True
        assert org.is_organization() is True

    def test_entity_serialization(self):
        """Test Entity serialization/deserialization."""
        entity = Entity("Sparkle", "PERSON")

        # Serialize
        data = entity.to_dict()
        assert data == {"text": "Sparkle", "type": "PERSON"}

        # Deserialize
        restored = Entity.from_dict(data)
        assert restored.text == "Sparkle"
        assert restored.type == "PERSON"

    def test_action_behavior(self):
        """Test Action smart object methods."""
        action = Action("steal")
        helper = Action("be")

        assert action.is_past_tense_marker() is False
        assert helper.is_past_tense_marker() is True

    def test_memory_stores_and_retrieves_smart_objects(self):
        """Test that Memory can store and retrieve entities/actions."""
        memory = Memory(content="Test")

        # Add entities
        memory.add_entity(Entity("Python", "LANGUAGE"))
        memory.add_entity(("Sparkle", "PERSON"))  # Also accepts tuple

        # Add actions
        memory.add_action(Action("code"))
        memory.add_action("debug")  # Also accepts string

        # Retrieve as smart objects
        entities = memory.get_entities()
        assert len(entities) == 2
        assert all(isinstance(e, Entity) for e in entities)
        assert entities[0].text == "Python"

        actions = memory.get_actions()
        assert len(actions) == 2
        assert all(isinstance(a, Action) for a in actions)
        assert actions[1].lemma == "debug"


class TestDomainModelInteraction:
    """Test how domain models work together."""

    def test_memory_with_rich_features(self):
        """Test a memory with all features."""
        memory = Memory(content="Sparkle stole pizza from the counter yesterday")

        # Add user tags
        memory.add_tags("cats", "sparkle theft", "funny")

        # Simulate what the repository would do
        memory.add_entity(Entity("Sparkle", "PERSON"))  # Cat names often recognized as PERSON
        memory.add_entity(Entity("yesterday", "DATE"))
        memory.add_action(Action("steal"))

        # Check the memory has all features
        assert len(memory.get_tags()) == 3
        assert len(memory.metadata["entities"]) == 2
        assert len(memory.metadata["actions"]) == 1

        # Tags should be normalized internally
        tags = memory.get_tags()
        assert "cat" in tags  # "cats" -> "cat"
        assert "funny" in tags
        assert "sparkle-theft" in tags
