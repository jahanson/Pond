"""Memory repository for database operations."""
from __future__ import annotations

import numpy as np
from pendulum import DateTime

from .entities import Action, Entity
from .memory import Memory


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
