"""Memory domain model."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pendulum

from .base import MAX_CONTENT_LENGTH, ValidationError
from .entities import Action, Entity
from .tag import Tag


@dataclass
class Memory:
    """A single memory with flexible metadata storage."""

    # Core fields (as columns)
    id: int | None = None
    content: str = ""
    embedding: np.ndarray | None = None
    forgotten: bool = False

    # Flexible metadata (JSONB)
    metadata: dict = field(default_factory=lambda: {
        "created_at": pendulum.now("UTC").isoformat(),
        "tags": set(),  # Stored as set internally, serialized as list
        "entities": [],
        "actions": [],
    })

    def __post_init__(self):
        """Validate the memory after creation."""
        # Always validate content (even empty string)
        self.content = self._validate_content(self.content)

    @staticmethod
    def _validate_content(content: str) -> str:
        """Validate memory content according to spec rules.

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

    def add_tag(self, tag: str | Tag) -> None:
        """Add a tag to metadata, normalized and deduplicated."""
        if isinstance(tag, str):
            tag = Tag(tag)

        if "tags" not in self.metadata:
            self.metadata["tags"] = set()

        self.metadata["tags"].add(tag.normalized)

    def add_tags(self, *tags: str | Tag) -> None:
        """Add multiple tags."""
        for tag in tags:
            self.add_tag(tag)

    def get_tags(self) -> list[str]:
        """Get all normalized tags."""
        tags = self.metadata.get("tags", set())
        # Return as sorted list for consistent ordering
        return sorted(tags)

    def add_entity(self, entity: Entity | tuple[str, str]) -> None:
        """Add an entity to metadata."""
        if isinstance(entity, tuple):
            entity = Entity(text=entity[0], type=entity[1])

        if "entities" not in self.metadata:
            self.metadata["entities"] = []

        serialized = entity.to_dict()
        if serialized not in self.metadata["entities"]:
            self.metadata["entities"].append(serialized)

    def get_entities(self) -> list[Entity]:
        """Get entities as smart objects."""
        return [Entity.from_dict(e) for e in self.metadata.get("entities", [])]

    def add_action(self, action: Action | str) -> None:
        """Add an action to metadata."""
        if isinstance(action, str):
            action = Action(lemma=action)

        if "actions" not in self.metadata:
            self.metadata["actions"] = []

        serialized = action.to_dict()
        if serialized not in self.metadata["actions"]:
            self.metadata["actions"].append(serialized)

    def get_actions(self) -> list[Action]:
        """Get actions as smart objects."""
        return [Action.from_dict(a) for a in self.metadata.get("actions", [])]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Convert sets to lists for JSONB serialization
        metadata = self.metadata.copy()
        if "tags" in metadata and isinstance(metadata["tags"], set):
            metadata["tags"] = sorted(metadata["tags"])  # Sort for consistency

        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "forgotten": self.forgotten,
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Memory:
        """Create Memory from dictionary (e.g., from database).

        Converts list representations back to sets where appropriate.
        """
        metadata = data.get("metadata", {}).copy()

        # Convert tags list back to set
        if "tags" in metadata and isinstance(metadata["tags"], list):
            metadata["tags"] = set(metadata["tags"])

        # Handle embedding
        embedding = None
        if data.get("embedding") is not None:
            embedding = np.array(data["embedding"])

        return cls(
            id=data.get("id"),
            content=data["content"],
            embedding=embedding,
            forgotten=data.get("forgotten", False),
            metadata=metadata,
        )
