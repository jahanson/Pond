"""Tests for feature extraction in MemoryRepository."""
import pytest

from pond.domain import Memory, MemoryRepository


class TestFeatureExtraction:
    """Test entity, action, and auto-tag extraction."""

    @pytest.fixture
    def repository(self):
        """Create a repository with mocked pool."""
        return MemoryRepository(pool=None, tenant="test")

    def test_extract_entities(self, repository):
        """Test entity extraction from text."""
        memory = Memory(content="John Smith works at Microsoft in San Francisco.")
        repository._extract_features(memory)

        entities = memory.get_entities()
        entity_dict = {(e.text, e.type) for e in entities}

        # Should extract person, org, and location
        assert ("John Smith", "PERSON") in entity_dict
        assert ("Microsoft", "ORG") in entity_dict  # More likely to be recognized
        assert ("San Francisco", "GPE") in entity_dict

    def test_extract_actions(self, repository):
        """Test action extraction from text."""
        memory = Memory(content="Sparkle stole pizza and then ran away quickly.")
        repository._extract_features(memory)

        actions = memory.get_actions()
        lemmas = {a.lemma for a in actions}

        # Should extract lemmatized verbs (not auxiliaries)
        assert "steal" in lemmas  # stole -> steal
        assert "run" in lemmas    # ran -> run
        assert len(lemmas) == 2   # No auxiliaries or stop words

    def test_extract_actions_filters_helpers(self, repository):
        """Test that helper verbs are extracted but can be identified."""
        memory = Memory(content="I have been working on this project.")
        repository._extract_features(memory)

        actions = memory.get_actions()
        lemmas = {a.lemma for a in actions}

        # Should extract all verbs and auxiliaries
        assert "have" in lemmas
        assert "be" in lemmas
        assert "work" in lemmas

        # But we can identify helpers
        helpers = [a for a in actions if a.is_past_tense_marker()]
        assert len(helpers) >= 2  # have, be

    def test_auto_tags_from_entities(self, repository):
        """Test auto-tag generation from entities."""
        memory = Memory(content="Python conference happening in Seattle next week.")
        memory.add_tags("events", "travel")  # User tags

        repository._extract_features(memory)

        tags = set(memory.get_tags())

        # Should include user tags
        assert "event" in tags  # events -> event (normalized)
        assert "travel" in tags

        # Should include entity-based auto-tags
        # Note: "Python conference" is extracted as a noun chunk
        assert "seattle" in tags
        assert any("python" in tag or "conference" in tag for tag in tags)

        # Should have 3-5 auto-tags total
        auto_tag_count = len(tags) - 2  # minus user tags
        assert 1 <= auto_tag_count <= 5

    def test_auto_tags_conservative(self, repository):
        """Test that auto-tagging is conservative."""
        # Short content with limited extractable features
        memory = Memory(content="It was good.")
        repository._extract_features(memory)

        tags = memory.get_tags()

        # Should not generate tags from pronouns or common words
        assert "it" not in tags
        assert "was" not in tags

        # Might generate "good" or might not - be conservative
        assert len(tags) <= 1

    def test_auto_tags_from_noun_chunks(self, repository):
        """Test auto-tag generation from noun chunks."""
        memory = Memory(content="The machine learning model improved customer satisfaction scores significantly.")
        repository._extract_features(memory)

        tags = set(memory.get_tags())

        # Should include meaningful noun chunks
        # Note: exact tags depend on spaCy's chunking
        meaningful_tags = tags - {"the", "a", "an"}  # Remove articles if any
        assert len(meaningful_tags) >= 2  # At least some noun chunks
        assert len(meaningful_tags) <= 5  # But not too many

    def test_no_duplicate_tags(self, repository):
        """Test that auto-tags don't duplicate user tags."""
        memory = Memory(content="Learning Python programming at the Python conference.")
        memory.add_tags("python", "learning")

        repository._extract_features(memory)

        tags = memory.get_tags()

        # Should not have duplicates (sets handle this)
        assert len(tags) == len(set(tags))

        # Python appears in content but was already a user tag
        python_count = tags.count("python")
        assert python_count == 1

    def test_spanish_content(self, repository):
        """Test extraction with non-English content."""
        memory = Memory(content="Hola, ¿cómo estás? Me llamo Juan.")
        repository._extract_features(memory)

        # Should handle gracefully even if English model
        # May not extract entities correctly but shouldn't crash
        entities = memory.get_entities()
        actions = memory.get_actions()
        tags = memory.get_tags()

        # Basic sanity checks
        assert isinstance(entities, list)
        assert isinstance(actions, list)
        assert isinstance(tags, list)

    def test_code_snippet_extraction(self, repository):
        """Test extraction from content with code."""
        memory = Memory(content="Fixed the bug in user.save() method by adding validation.")
        repository._extract_features(memory)

        actions = memory.get_actions()
        lemmas = {a.lemma for a in actions}

        # Should extract natural language verbs
        assert "fix" in lemmas  # Fixed -> fix
        assert "add" in lemmas  # adding -> add
        assert "save" in lemmas or len(lemmas) >= 2  # Might extract save

    def test_entity_types(self, repository):
        """Test that entity types are preserved correctly."""
        memory = Memory(content="Microsoft released Windows 11 on October 5, 2021.")
        repository._extract_features(memory)

        entities = memory.get_entities()

        # Check entity types
        for entity in entities:
            if entity.text == "Microsoft":
                assert entity.type == "ORG"
                assert entity.is_organization()
            elif entity.text == "October 5, 2021":
                assert entity.type == "DATE"
            elif entity.text == "Windows 11":
                # Might be PRODUCT or other type
                assert entity.type in ["PRODUCT", "ORG", "MISC"]
