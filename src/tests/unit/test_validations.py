"""
Unit tests for input validation and limits.
"""
import pytest

from pond.services.validation import (
    validate_memory_length,
    normalize_tag,
    validate_tags
)


class TestMemoryValidation:
    """Test memory content validation."""
    
    def test_memory_within_limit(self):
        """Test that normal memories pass validation."""
        memory = "Sparkle stole pizza from the counter"
        assert validate_memory_length(memory) is True
    
    def test_memory_at_limit(self):
        """Test memory exactly at character limit."""
        memory = "x" * 7500  # Exactly at limit
        assert validate_memory_length(memory) is True
    
    def test_memory_over_limit(self):
        """Test that oversized memories are rejected."""
        memory = "x" * 7501  # Just over limit
        assert validate_memory_length(memory) is False
    
    def test_empty_memory_rejected(self):
        """Test that empty memories are rejected."""
        assert validate_memory_length("") is False
        assert validate_memory_length("   ") is False  # Just whitespace


class TestTagNormalization:
    """Test tag normalization and validation."""
    
    def test_basic_normalization(self):
        """Test basic tag normalization."""
        assert normalize_tag("Python") == "python"
        assert normalize_tag("UPPERCASE") == "uppercase"
        assert normalize_tag("  spaces  ") == "spaces"
    
    def test_pluralization(self):
        """Test singular form conversion."""
        assert normalize_tag("cats") == "cat"
        assert normalize_tag("memories") == "memory"
        assert normalize_tag("children") == "child"
        assert normalize_tag("people") == "person"
    
    def test_space_handling(self):
        """Test conversion of spaces to hyphens."""
        assert normalize_tag("Python Tips") == "python-tip"
        assert normalize_tag("machine learning") == "machine-learning"
        assert normalize_tag("multiple   spaces") == "multiple-spaces"
    
    def test_special_character_removal(self):
        """Test removal of special characters."""
        assert normalize_tag("python@tips") == "pythontips"
        assert normalize_tag("c++") == "c"
        assert normalize_tag("node.js") == "nodejs"
    
    def test_already_normalized(self):
        """Test that normalized tags aren't changed."""
        assert normalize_tag("python") == "python"
        assert normalize_tag("sparkle-theft") == "sparkle-theft"


class TestTagValidation:
    """Test tag list validation."""
    
    def test_valid_tag_list(self):
        """Test that valid tag lists pass."""
        tags = ["python", "debugging", "async"]
        assert validate_tags(tags) is True
    
    def test_too_many_tags(self):
        """Test rejection of too many tags."""
        tags = [f"tag{i}" for i in range(21)]  # 21 tags
        assert validate_tags(tags) is False
    
    def test_empty_tags_allowed(self):
        """Test that empty tag list is valid."""
        assert validate_tags([]) is True
        assert validate_tags(None) is True
    
    def test_duplicate_tags_handled(self):
        """Test that duplicate tags are handled."""
        tags = ["python", "Python", "PYTHON"]
        normalized = [normalize_tag(tag) for tag in tags]
        unique_tags = list(set(normalized))
        assert len(unique_tags) == 1
        assert unique_tags[0] == "python"