"""Domain models for Pond - the core business objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypeVar

import numpy as np
import pendulum
from pendulum import DateTime


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


# Constants from the old validation service
MAX_CONTENT_LENGTH = 7500


T = TypeVar('T', bound='MetadataItem')


class MetadataItem(Protocol):
    """Protocol for items that can be stored in Memory metadata."""

    def to_dict(self) -> dict:
        """Serialize to dict for JSONB storage."""
        ...

    @classmethod
    def from_dict(cls: type[T], data: dict) -> T:
        """Hydrate from JSONB storage."""
        ...


class Tag:
    """A tag that knows how to normalize itself."""

    # Class-level spaCy model (shared across all tags)
    _nlp = None

    def __init__(self, raw: str):
        """Create a tag from raw text."""
        self.raw = raw.strip()
        self._normalized: str | None = None

    @classmethod
    def _get_nlp(cls):
        """Lazy load spaCy model once for all tags."""
        if cls._nlp is None:
            import spacy
            # Only load what we need for lemmatization
            cls._nlp = spacy.load("en_core_web_lg", disable=["parser", "ner"])
        return cls._nlp

    @property
    def normalized(self) -> str:
        """Get the normalized form of this tag (cached)."""
        if self._normalized is None:
            self._normalized = self._normalize()
        return self._normalized

    def _normalize(self) -> str:
        """Normalize tag using spaCy lemmatization with alphabetization."""
        import re

        text = self.raw.lower()
        if not text:
            return ""

        # Process with spaCy
        doc = self._get_nlp()(text)

        # Get lemmas, excluding stopwords and punctuation
        lemmas = []
        for token in doc:
            if token.is_stop or token.is_punct:
                continue

            # Clean special characters
            lemma = re.sub(r'[^a-z0-9-]', '', token.lemma_.strip())
            if lemma:
                lemmas.append(lemma)

        # If no tokens remain, clean the original
        if not lemmas:
            cleaned = re.sub(r'[^a-z0-9-]', '', text)
            return cleaned.replace(" ", "-") if cleaned else text.replace(" ", "-")

        # Sort alphabetically and join
        return "-".join(sorted(lemmas))

    def __eq__(self, other) -> bool:
        """Tags are equal if they normalize to the same string."""
        if not isinstance(other, Tag):
            return False
        return self.normalized == other.normalized

    def __hash__(self) -> int:
        """Hash based on normalized form for use in sets."""
        return hash(self.normalized)

    def __repr__(self) -> str:
        return f"Tag({self.raw!r})"

    def __str__(self) -> str:
        return self.raw


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
    def from_dict(cls, data: dict) -> Entity:
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
    def from_dict(cls, data: dict) -> Action:
        """Hydrate from JSONB storage."""
        return cls(lemma=data["lemma"])


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
        "tags": [],
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
            self.metadata["tags"] = []

        normalized = tag.normalized
        if normalized not in self.metadata["tags"]:
            self.metadata["tags"].append(normalized)

    def add_tags(self, *tags: str | Tag) -> None:
        """Add multiple tags."""
        for tag in tags:
            self.add_tag(tag)

    def get_tags(self) -> list[str]:
        """Get all normalized tags."""
        return self.metadata.get("tags", [])

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
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "forgotten": self.forgotten,
            "metadata": self.metadata,
        }


class MemoryRepository:
    """Repository for storing and retrieving memories."""

    def __init__(self, pool, tenant: str):
        """Initialize with database pool and tenant name."""
        self.pool = pool
        self.tenant = tenant
        self._nlp = None

    @property
    def nlp(self):
        """Lazy load spaCy model for entity/action extraction."""
        if self._nlp is None:
            import spacy
            self._nlp = spacy.load("en_core_web_lg")
        return self._nlp

    async def store(self, content: str, user_tags: list[str]) -> tuple[Memory, list[Memory]]:
        """Store a memory and return it with splash memories.

        Returns:
            (stored_memory, splash_memories)
        """
        # Create memory object
        memory = Memory(content=content)

        # Add user tags
        memory.add_tags(*user_tags)

        # Extract features from content
        self._extract_features(memory)

        # Get embedding
        memory.embedding = await self._get_embedding(content)

        # Store in database
        memory.id = await self._store_in_db(memory)

        # Get splash
        splash = await self._get_splash(memory)

        return memory, splash

    def _extract_features(self, memory: Memory) -> None:
        """Extract entities, actions, and auto-tags from memory content."""
        doc = self.nlp(memory.content)

        # Extract entities
        for ent in doc.ents:
            memory.add_entity(Entity(text=ent.text, type=ent.label_))

        # Extract actions (verbs)
        for token in doc:
            if token.pos_ == "VERB" and not token.is_stop:
                memory.add_action(Action(lemma=token.lemma_))

        # Generate auto-tags (3-5 from entities and noun chunks)
        auto_tags = []

        # Add entity-based tags
        entities = memory.metadata.get("entities", [])
        for ent in entities[:3]:
            auto_tags.append(ent["text"])

        # Add noun chunk tags
        for chunk in doc.noun_chunks:
            if len(auto_tags) < 5:
                # Skip if it's just a pronoun or too common
                if chunk.root.pos_ != "PRON" and not chunk.root.is_stop:
                    auto_tags.append(chunk.text)

        # Add the auto-tags to the memory
        memory.add_tags(*auto_tags)

    async def _get_embedding(self, content: str) -> np.ndarray:
        """Get embedding from Ollama."""
        # TODO: Implement actual Ollama call
        return np.random.rand(768)  # Placeholder

    async def _store_in_db(self, memory: Memory) -> int:
        """Store memory in database, return ID."""
        # TODO: Implement actual DB storage
        return 42  # Placeholder

    async def _get_splash(self, memory: Memory) -> list[Memory]:
        """Get memories in the similarity sweet spot (0.7-0.9)."""
        # TODO: Implement actual similarity search
        return []  # Placeholder

    async def search(self, query: str, limit: int = 10) -> list[Memory]:
        """Search for memories by semantic similarity."""
        # TODO: Implement
        pass

    async def get_recent(self, since: DateTime, limit: int = 10) -> list[Memory]:
        """Get recent memories since a given time."""
        # TODO: Implement
        pass
