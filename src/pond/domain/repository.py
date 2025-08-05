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

        # Extract actions (lemmatized verbs from all tenses)
        for token in doc:
            if token.pos_ in ["VERB", "AUX"]:
                # Include all verbs and auxiliaries
                # The Action class has is_past_tense_marker() to identify helpers
                memory.add_action(Action(lemma=token.lemma_))

        # Generate auto-tags (3-5 conservative, from entities/noun chunks/nouns)
        auto_tags = []

        # Get existing user tags to avoid duplicates
        existing_tags = set(memory.get_tags())

        # 1. Add entity-based tags (most reliable)
        entities = memory.get_entities()
        for ent in entities[:3]:  # Limit to 3 entity tags
            # Only add if it won't be a duplicate after normalization
            if ent.text and ent.text not in existing_tags:
                auto_tags.append(ent.text)

        # 2. Add noun chunk tags if we need more
        if len(auto_tags) < 5:
            for chunk in doc.noun_chunks:
                if len(auto_tags) >= 5:
                    break

                # Be conservative - skip pronouns, single stopwords, very short chunks
                if (chunk.root.pos_ == "PRON" or
                    (len(chunk) == 1 and chunk.root.is_stop) or
                    len(chunk.text) < 3):
                    continue

                # Skip if already in auto_tags or would duplicate user tag
                if chunk.text not in auto_tags and chunk.text not in existing_tags:
                    auto_tags.append(chunk.text)

        # 3. If still need more, look at significant individual nouns
        if len(auto_tags) < 3:  # Ensure at least 3 tags if possible
            for token in doc:
                if len(auto_tags) >= 5:
                    break

                # Only proper nouns or nouns that aren't stop words
                if (token.pos_ in ["PROPN", "NOUN"] and
                    not token.is_stop and
                    len(token.text) > 2 and
                    token.text not in auto_tags and
                    token.text not in existing_tags):
                    auto_tags.append(token.text)

        # Add the auto-tags to the memory
        if auto_tags:
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
