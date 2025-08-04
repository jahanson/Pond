"""Domain models for Pond - the core business objects."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pendulum
from pendulum import DateTime


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


# Constants from the old validation service
MAX_CONTENT_LENGTH = 7500


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
    """An entity extracted from memory content."""
    text: str
    type: str  # PERSON, ORG, LOC, etc.

    def __str__(self) -> str:
        return self.text


@dataclass
class Action:
    """An action (verb) extracted from memory content."""
    lemma: str  # Base form of the verb

    def __str__(self) -> str:
        return self.lemma


@dataclass
class Memory:
    """A single memory with all its extracted features."""

    # Core fields
    id: int | None = None
    content: str = ""
    created_at: DateTime = field(default_factory=lambda: pendulum.now("UTC"))

    # Extracted features
    tags: list[Tag] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)

    # Embedding (set later)
    embedding: np.ndarray | None = None

    # Metadata
    active: bool = True

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

    def add_tags(self, *tags: str | Tag) -> None:
        """Add tags, deduplicating in normalized space."""
        for tag in tags:
            if isinstance(tag, str):
                tag = Tag(tag)

            # Only add if not already present (uses Tag.__eq__)
            if tag not in self.tags:
                self.tags.append(tag)

    def get_normalized_tags(self) -> list[str]:
        """Get all normalized tag strings."""
        return [tag.normalized for tag in self.tags]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "tags": [tag.raw for tag in self.tags],
            "entities": [{"text": e.text, "type": e.type} for e in self.entities],
            "actions": [action.lemma for action in self.actions],
            "active": self.active,
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
            memory.entities.append(Entity(text=ent.text, type=ent.label_))

        # Extract actions (verbs)
        for token in doc:
            if token.pos_ == "VERB" and not token.is_stop:
                memory.actions.append(Action(lemma=token.lemma_))

        # Generate auto-tags (3-5 from entities and noun chunks)
        auto_tags = []

        # Add entity-based tags
        for ent in memory.entities[:3]:
            auto_tags.append(ent.text)

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
