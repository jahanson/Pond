"""Entity and Action domain models."""

from dataclasses import dataclass


@dataclass
class Entity:
    """An entity extracted from text."""

    text: str
    type: str  # PERSON, ORG, LOC, etc.

    def is_person(self) -> bool:
        """Check if this is a person entity."""
        return self.type in ["PERSON", "PER"]

    def is_location(self) -> bool:
        """Check if this is a location entity."""
        return self.type in ["LOC", "GPE", "FAC"]

    def is_organization(self) -> bool:
        """Check if this is an organization entity."""
        return self.type in ["ORG", "COMPANY"]

    def to_dict(self) -> dict:
        """Serialize for JSONB storage."""
        return {"text": self.text, "type": self.type}

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        """Hydrate from JSONB storage."""
        return cls(text=data["text"], type=data["type"])


@dataclass
class Action:
    """An action (verb) extracted from text."""

    lemma: str

    def is_past_tense_marker(self) -> bool:
        """Check if this is a common past tense helper verb."""
        return self.lemma in ["be", "have", "do", "will", "would", "could", "should"]

    def to_dict(self) -> dict:
        """Serialize for JSONB storage."""
        return {"lemma": self.lemma}

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        """Hydrate from JSONB storage."""
        return cls(lemma=data["lemma"])
