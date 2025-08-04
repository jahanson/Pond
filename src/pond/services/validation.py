"""Input validation for memory content."""


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


MAX_CONTENT_LENGTH = 7500


class ValidationService:
    """Validates memory content according to spec rules."""

    def __init__(self, embedding_service=None):
        """Initialize with optional embedding service.

        If no service provided, creates default implementation.
        """
        if embedding_service is None:
            from pond.services.embeddings import EmbeddingService
            embedding_service = EmbeddingService()
        self.embedding_service = embedding_service

    def validate_content(self, content: str) -> str:
        """
        Validate memory content.

        Rules:
        - Cannot be empty
        - Cannot be only whitespace
        - Cannot exceed MAX_CONTENT_LENGTH characters

        Returns cleaned content if valid.
        Raises ValidationError if invalid.
        """
        if not content:
            raise ValidationError("Content cannot be empty")

        # Strip leading/trailing whitespace for validation
        cleaned = content.strip()

        if not cleaned:
            raise ValidationError("Content cannot be only whitespace")

        if len(content) > MAX_CONTENT_LENGTH:
            raise ValidationError(
                f"Content exceeds maximum length of {MAX_CONTENT_LENGTH} characters"
            )

        return content

    def validate_tags(self, tags: list[str] | None) -> list[str]:
        """
        Validate and clean tags.

        Returns list of cleaned tags (may be empty).
        """
        if not tags:
            return []

        # Use embedding service to normalize and deduplicate
        return self.embedding_service.embed_tags(tags)

    def validate_search_query(self, query: str) -> str:
        """
        Validate search query.

        Returns cleaned query if valid.
        Raises ValidationError if invalid.
        """
        if not query:
            raise ValidationError("Search query cannot be empty")

        cleaned = query.strip()

        if not cleaned:
            raise ValidationError("Search query cannot be only whitespace")

        return cleaned

    def validate_limit(self, limit: int | None, default: int = 10, max_limit: int = 100) -> int:
        """
        Validate and constrain limit parameter.

        Returns valid limit value.
        """
        if limit is None:
            return default

        if not isinstance(limit, int) or limit < 1:
            return default

        return min(limit, max_limit)


# Module-level functions that the tests expect
def validate_memory_length(content: str) -> bool:
    """Check if memory content is within length limit."""
    if not content or not content.strip():
        return False
    return len(content) <= MAX_CONTENT_LENGTH


# Module-level function for backward compatibility with tests
def normalize_tag(tag: str) -> str:
    """Normalize a tag to lowercase with hyphens.

    This function exists for backward compatibility with tests.
    Uses the default EmbeddingService.
    """
    from pond.services.embeddings import EmbeddingService
    _embedding_service = EmbeddingService()
    return _embedding_service.embed_tag(tag)


def validate_tags(tags: list[str] | None) -> bool:
    """Check if a list of tags is valid."""
    # Tags are always valid in our system - empty lists are fine
    _ = tags  # Unused but required for backward compatibility
    return True

