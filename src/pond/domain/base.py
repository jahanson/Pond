"""Base classes and protocols for domain models."""

from typing import Protocol, TypeVar


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


# Constants
MAX_CONTENT_LENGTH = 7500


T = TypeVar("T", bound="MetadataItem")


class MetadataItem(Protocol):
    """Protocol for items that can be stored in Memory metadata."""

    def to_dict(self) -> dict:
        """Serialize to dict for JSONB storage."""
        ...

    @classmethod
    def from_dict(cls: type[T], data: dict) -> T:
        """Hydrate from JSONB storage."""
        ...
