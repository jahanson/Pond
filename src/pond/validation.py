"""Backward compatibility module for validation functions."""
from pond.models import MAX_CONTENT_LENGTH


def validate_memory_length(content: str) -> bool:
    """Check if memory content is within length limit.

    This function exists for backward compatibility with tests.
    """
    if not content or not content.strip():
        return False
    return len(content) <= MAX_CONTENT_LENGTH


def normalize_tag(tag: str) -> str:
    """Normalize a tag to lowercase with hyphens.

    This function exists for backward compatibility with tests.
    Uses the Tag domain model.
    """
    from pond.models import Tag
    return Tag(tag).normalized


def validate_tags(tags: list[str] | None) -> bool:
    """Check if a list of tags is valid.

    Tags are always valid in our system - empty lists are fine.
    """
    _ = tags  # Unused but required for backward compatibility
    return True
